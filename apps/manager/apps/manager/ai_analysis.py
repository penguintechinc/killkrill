"""
AI-Powered Metric Analysis Module for KillKrill Manager (Enterprise Edition)
Integrates with OpenAI-compatible endpoints to analyze metrics and performance issues
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
import requests
from prometheus_client import Counter, Histogram
from py4web import action, request, response
from py4web.utils.cors import CORS
from pydal import Field

# Enterprise license check
from . import get_db

# AI Configuration
AI_ENDPOINT_URL = os.environ.get(
    "AI_ENDPOINT_URL", "https://api.anthropic.com/v1/messages"
)
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "claude-3-haiku-20240307")
AI_PROVIDER = os.environ.get(
    "AI_PROVIDER", "anthropic"
)  # anthropic, openai, ollama, etc.

# Analysis configuration
ANALYSIS_INTERVAL_HOURS = int(
    os.environ.get("AI_ANALYSIS_INTERVAL", "4")
)  # Every 4 hours
ANALYSIS_LOOKBACK_HOURS = int(
    os.environ.get("AI_ANALYSIS_LOOKBACK", "24")
)  # Look back 24 hours

# Metrics
ai_analysis_requests = Counter(
    "killkrill_ai_analysis_requests_total",
    "AI analysis requests",
    ["provider", "status"],
)
ai_analysis_duration = Histogram(
    "killkrill_ai_analysis_duration_seconds", "AI analysis duration"
)


class AIMetricsAnalyzer:
    """AI-powered metrics analyzer for enterprise deployments"""

    def __init__(self, db):
        self.db = db
        self._setup_tables()

    def _setup_tables(self):
        """Setup AI analysis tables"""
        try:
            # AI analysis results
            self.db.define_table(
                "ai_analyses",
                Field("analysis_id", "string"),
                Field("timestamp", "datetime", default=datetime.utcnow),
                Field(
                    "analysis_type", "string"
                ),  # performance, security, capacity, etc.
                Field("severity", "string"),  # low, medium, high, critical
                Field("summary", "text"),
                Field("recommendations", "text"),
                Field("affected_components", "text"),  # JSON array
                Field("metrics_analyzed", "text"),  # JSON object
                Field("confidence_score", "double"),
                Field("is_acknowledged", "boolean", default=False),
                Field("acknowledged_by", "string"),
                Field("acknowledged_at", "datetime"),
                migrate=True,
            )

            # AI analysis configuration
            self.db.define_table(
                "ai_config",
                Field("config_key", "string"),
                Field("config_value", "text"),
                Field("updated_at", "datetime", default=datetime.utcnow),
                migrate=True,
            )

            # Performance baselines for comparison
            self.db.define_table(
                "performance_baselines",
                Field("component", "string"),
                Field("metric_name", "string"),
                Field("baseline_value", "double"),
                Field("threshold_warning", "double"),
                Field("threshold_critical", "double"),
                Field("last_updated", "datetime", default=datetime.utcnow),
                migrate=True,
            )

            self.db.commit()
        except Exception as e:
            print(f"AI analysis table setup: {e}")

    def check_enterprise_license(self) -> bool:
        """Check if enterprise features are enabled"""
        # TODO: Integrate with PenguinTech License Server
        license_key = os.environ.get("LICENSE_KEY", "")
        if not license_key:
            return False

        try:
            # Simplified license check - in production, validate with license server
            return (
                license_key.startswith("PENG-") and "ENTERPRISE" in license_key.upper()
            )
        except:
            return False

    async def collect_prometheus_metrics(self) -> Dict[str, Any]:
        """Collect metrics from Prometheus for analysis"""
        prometheus_url = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
        metrics_queries = {
            "cpu_usage": 'avg(100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))',
            "memory_usage": "avg((1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100)",
            "disk_usage": 'avg(100 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes * 100))',
            "network_errors": "sum(rate(node_network_receive_errs_total[5m]) + rate(node_network_transmit_errs_total[5m]))",
            "container_restarts": "sum(rate(kube_pod_container_status_restarts_total[1h]))",
            "fleet_agents_online": "count(fleet_host_status == 1)",
            "elasticsearch_health": "elasticsearch_cluster_health_status",
            "redis_memory_usage": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
            "log_ingestion_rate": "sum(rate(killkrill_logs_received_total[5m]))",
            "metrics_ingestion_rate": "sum(rate(killkrill_metrics_received_total[5m]))",
        }

        collected_metrics = {}
        try:
            async with aiohttp.ClientSession() as session:
                for metric_name, query in metrics_queries.items():
                    try:
                        url = f"{prometheus_url}/api/v1/query"
                        params = {"query": query}

                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data["data"]["result"]:
                                    value = float(data["data"]["result"][0]["value"][1])
                                    collected_metrics[metric_name] = value
                    except Exception as e:
                        print(f"Error collecting {metric_name}: {e}")

        except Exception as e:
            print(f"Error collecting Prometheus metrics: {e}")

        return collected_metrics

    async def analyze_with_ai(
        self, metrics_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send metrics to AI for analysis"""
        if not self.check_enterprise_license():
            return None

        try:
            analysis_prompt = self._build_analysis_prompt(metrics_data)

            if AI_PROVIDER == "anthropic":
                return await self._analyze_with_anthropic(analysis_prompt)
            elif AI_PROVIDER == "openai":
                return await self._analyze_with_openai(analysis_prompt)
            elif AI_PROVIDER == "ollama":
                return await self._analyze_with_ollama(analysis_prompt)
            else:
                return await self._analyze_generic(analysis_prompt)

        except Exception as e:
            print(f"AI analysis error: {e}")
            ai_analysis_requests.labels(provider=AI_PROVIDER, status="error").inc()
            return None

    def _build_analysis_prompt(self, metrics_data: Dict[str, Any]) -> str:
        """Build analysis prompt for AI"""
        prompt = f"""
You are an expert system administrator analyzing infrastructure metrics for a production system running KillKrill (centralized logging and metrics platform) with Fleet device management.

Current System Metrics (last 24 hours):
{json.dumps(metrics_data, indent=2)}

Please analyze these metrics and provide:

1. PERFORMANCE ISSUES: Identify any performance problems or bottlenecks
2. CAPACITY PLANNING: Highlight any resources approaching limits
3. SECURITY CONCERNS: Note any unusual patterns that might indicate security issues
4. OPTIMIZATION OPPORTUNITIES: Suggest improvements for better performance
5. ALERTS: Classify severity as LOW, MEDIUM, HIGH, or CRITICAL

For each issue found, provide:
- Clear description of the problem
- Impact assessment
- Specific recommendations with actionable steps
- Estimated priority/urgency

Respond in JSON format with the following structure:
{{
  "summary": "Brief overall assessment",
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "confidence_score": 0.85,
  "issues": [
    {{
      "type": "performance|capacity|security|optimization",
      "title": "Issue title",
      "description": "Detailed description",
      "severity": "LOW|MEDIUM|HIGH|CRITICAL",
      "affected_components": ["component1", "component2"],
      "recommendations": ["action1", "action2"],
      "metrics_evidence": {{"metric_name": "value"}}
    }}
  ],
  "recommendations": [
    "Overall recommendation 1",
    "Overall recommendation 2"
  ]
}}

Focus on actionable insights that a system administrator can implement.
"""
        return prompt

    async def _analyze_with_anthropic(self, prompt: str) -> Dict[str, Any]:
        """Analyze with Anthropic Claude"""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": AI_API_KEY,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": AI_MODEL,
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                AI_ENDPOINT_URL, headers=headers, json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ai_analysis_requests.labels(
                        provider="anthropic", status="success"
                    ).inc()

                    # Extract JSON from response
                    content = data["content"][0]["text"]
                    return self._parse_ai_response(content)
                else:
                    ai_analysis_requests.labels(
                        provider="anthropic", status="error"
                    ).inc()
                    return None

    async def _analyze_with_openai(self, prompt: str) -> Dict[str, Any]:
        """Analyze with OpenAI GPT"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY}",
        }

        payload = {
            "model": AI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert system administrator analyzing infrastructure metrics.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4000,
            "temperature": 0.1,
        }

        openai_url = AI_ENDPOINT_URL or "https://api.openai.com/v1/chat/completions"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                openai_url, headers=headers, json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ai_analysis_requests.labels(
                        provider="openai", status="success"
                    ).inc()

                    content = data["choices"][0]["message"]["content"]
                    return self._parse_ai_response(content)
                else:
                    ai_analysis_requests.labels(provider="openai", status="error").inc()
                    return None

    async def _analyze_with_ollama(self, prompt: str) -> Dict[str, Any]:
        """Analyze with local Ollama instance"""
        payload = {"model": AI_MODEL, "prompt": prompt, "stream": False}

        ollama_url = AI_ENDPOINT_URL or "http://localhost:11434/api/generate"

        async with aiohttp.ClientSession() as session:
            async with session.post(ollama_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    ai_analysis_requests.labels(
                        provider="ollama", status="success"
                    ).inc()

                    content = data["response"]
                    return self._parse_ai_response(content)
                else:
                    ai_analysis_requests.labels(provider="ollama", status="error").inc()
                    return None

    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """Parse AI response and extract JSON"""
        try:
            # Try to find JSON in the response
            start = content.find("{")
            end = content.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
            else:
                # Fallback if no JSON found
                return {
                    "summary": content[:500] + "..." if len(content) > 500 else content,
                    "severity": "MEDIUM",
                    "confidence_score": 0.5,
                    "issues": [],
                    "recommendations": [],
                }
        except json.JSONDecodeError:
            return {
                "summary": "AI analysis completed but response format was invalid",
                "severity": "LOW",
                "confidence_score": 0.3,
                "issues": [],
                "recommendations": ["Review AI provider configuration"],
            }

    async def perform_analysis(self) -> Optional[str]:
        """Perform complete AI analysis"""
        if not self.check_enterprise_license():
            return None

        try:
            with ai_analysis_duration.time():
                # Collect metrics
                metrics_data = await self.collect_prometheus_metrics()

                if not metrics_data:
                    return None

                # Analyze with AI
                analysis_result = await self.analyze_with_ai(metrics_data)

                if not analysis_result:
                    return None

                # Store results
                analysis_id = f"ai_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

                self.db.ai_analyses.insert(
                    analysis_id=analysis_id,
                    analysis_type="automated",
                    severity=analysis_result.get("severity", "MEDIUM"),
                    summary=analysis_result.get("summary", ""),
                    recommendations=json.dumps(
                        analysis_result.get("recommendations", [])
                    ),
                    affected_components=json.dumps(
                        [
                            issue.get("affected_components", [])
                            for issue in analysis_result.get("issues", [])
                        ]
                    ),
                    metrics_analyzed=json.dumps(metrics_data),
                    confidence_score=analysis_result.get("confidence_score", 0.5),
                )
                self.db.commit()

                return analysis_id

        except Exception as e:
            print(f"Error performing AI analysis: {e}")
            return None


# Initialize analyzer (will be done in main app)
ai_analyzer = None


def get_ai_analyzer(db):
    """Get AI analyzer instance"""
    global ai_analyzer
    if ai_analyzer is None:
        ai_analyzer = AIMetricsAnalyzer(db)
    return ai_analyzer


@action("ai/analyze", method=["POST"])
@action.uses(CORS())
def trigger_ai_analysis():
    """Manually trigger AI analysis (Enterprise only)"""
    try:
        analyzer = get_ai_analyzer(get_db())

        if not analyzer.check_enterprise_license():
            response.status = 403
            return {"error": "AI analysis requires Enterprise license"}

        # Run analysis asynchronously
        analysis_id = asyncio.run(analyzer.perform_analysis())

        if analysis_id:
            return {"success": True, "analysis_id": analysis_id}
        else:
            response.status = 500
            return {"error": "Analysis failed"}

    except Exception as e:
        response.status = 500
        return {"error": str(e)}


@action("ai/results")
@action("ai/results/<analysis_id>")
def get_ai_results(analysis_id=None):
    """Get AI analysis results"""
    try:
        analyzer = get_ai_analyzer(get_db())

        if not analyzer.check_enterprise_license():
            response.status = 403
            return {"error": "AI analysis requires Enterprise license"}

        db = get_db()

        if analysis_id:
            # Get specific analysis
            analysis = db(db.ai_analyses.analysis_id == analysis_id).select().first()
            if not analysis:
                response.status = 404
                return {"error": "Analysis not found"}

            return {
                "analysis_id": analysis.analysis_id,
                "timestamp": analysis.timestamp.isoformat(),
                "severity": analysis.severity,
                "summary": analysis.summary,
                "recommendations": json.loads(analysis.recommendations or "[]"),
                "affected_components": json.loads(analysis.affected_components or "[]"),
                "confidence_score": analysis.confidence_score,
                "is_acknowledged": analysis.is_acknowledged,
            }
        else:
            # Get recent analyses
            analyses = db(db.ai_analyses).select(
                orderby=~db.ai_analyses.timestamp, limitby=(0, 10)
            )

            return {
                "analyses": [
                    {
                        "analysis_id": a.analysis_id,
                        "timestamp": a.timestamp.isoformat(),
                        "severity": a.severity,
                        "summary": (
                            a.summary[:200] + "..."
                            if len(a.summary) > 200
                            else a.summary
                        ),
                        "confidence_score": a.confidence_score,
                        "is_acknowledged": a.is_acknowledged,
                    }
                    for a in analyses
                ]
            }

    except Exception as e:
        response.status = 500
        return {"error": str(e)}


@action("ai/acknowledge/<analysis_id>", method=["POST"])
@action.uses(CORS())
def acknowledge_analysis(analysis_id):
    """Acknowledge an AI analysis"""
    try:
        db = get_db()

        analysis = db(db.ai_analyses.analysis_id == analysis_id).select().first()
        if not analysis:
            response.status = 404
            return {"error": "Analysis not found"}

        # TODO: Get current user from session
        current_user = request.json.get("acknowledged_by", "admin")

        analysis.update_record(
            is_acknowledged=True,
            acknowledged_by=current_user,
            acknowledged_at=datetime.utcnow(),
        )
        db.commit()

        return {"success": True}

    except Exception as e:
        response.status = 500
        return {"error": str(e)}
