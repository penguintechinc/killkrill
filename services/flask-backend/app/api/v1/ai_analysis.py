"""
KillKrill Flask Backend - AI Analysis API Blueprint

Endpoints for AI-driven observability analysis with tiered access:
- FREE: Single Ollama endpoint with tinyllama model only
- LICENSED: Multiple endpoints, any model, Claude/OpenAI support

License required for:
- OpenAI API access
- Claude/Anthropic API access
- Models other than tinyllama
- Multiple Ollama endpoints
"""

from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, g
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List, Literal
from app.api.v1.schemas import APIResponse, ErrorResponse
from app.models.database import get_pydal_connection
from shared.licensing.client import PenguinTechLicenseClient
import os
import logging
import httpx

logger = logging.getLogger(__name__)

ai_analysis_bp = Blueprint('ai_analysis', __name__)

# =============================================================================
# Free Tier Constants
# =============================================================================

FREE_TIER_PROVIDER = 'ollama'
FREE_TIER_MODEL = 'tinyllama'
FREE_TIER_MAX_ENDPOINTS = 1
FREE_TIER_MAX_TOKENS = 2048

# Supported providers
SUPPORTED_PROVIDERS = ['ollama', 'openai', 'claude']
LICENSED_PROVIDERS = ['openai', 'claude']  # Require license

# =============================================================================
# Pydantic Schemas
# =============================================================================


class AIProviderCreate(BaseModel):
    """Schema for creating an AI provider configuration"""
    name: str = Field(min_length=1, max_length=128, description="Provider name")
    provider_type: Literal['ollama', 'openai', 'claude'] = Field(description="Provider type")
    endpoint_url: str = Field(min_length=1, max_length=512, description="API endpoint URL")
    api_key: Optional[str] = Field(default=None, max_length=256, description="API key (required for openai/claude)")
    model: str = Field(default='tinyllama', max_length=128, description="Default model to use")
    is_default: bool = Field(default=False, description="Set as default provider")


class AIChatRequest(BaseModel):
    """Schema for AI chat/completion request"""
    prompt: str = Field(min_length=1, max_length=32000, description="Input prompt")
    provider_id: Optional[int] = Field(default=None, description="Provider ID (uses default if not specified)")
    model: Optional[str] = Field(default=None, max_length=128, description="Model override")
    max_tokens: int = Field(default=1024, ge=1, le=32000, description="Max tokens in response")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    system_prompt: Optional[str] = Field(default=None, max_length=4000, description="System prompt")


class AIAnalyzeRequest(BaseModel):
    """Schema for AI analysis request"""
    data_source: str = Field(min_length=1, max_length=256, description="Data source identifier")
    analysis_type: Literal['general', 'anomaly_detection', 'correlation', 'forecasting'] = 'general'
    input_data: dict = Field(default_factory=dict, description="Input data for analysis")
    provider_id: Optional[int] = Field(default=None, description="Provider ID to use")


# =============================================================================
# License Client
# =============================================================================

_license_client = None


def get_license_client() -> PenguinTechLicenseClient:
    """Get or initialize license client"""
    global _license_client
    if _license_client is None:
        license_key = os.getenv('LICENSE_KEY', '')
        product = os.getenv('PRODUCT_NAME', 'killkrill')
        _license_client = PenguinTechLicenseClient(license_key, product)
    return _license_client


def has_valid_license() -> bool:
    """Check if user has a valid license for premium AI features"""
    try:
        client = get_license_client()
        return client.check_feature('ai_analysis')
    except Exception:
        return False


def is_free_tier_request(provider_type: str, model: str) -> bool:
    """Check if request qualifies for free tier (Ollama + tinyllama only)"""
    return (
        provider_type.lower() == FREE_TIER_PROVIDER and
        model.lower() == FREE_TIER_MODEL
    )


# =============================================================================
# Decorators
# =============================================================================


def requires_ai_access(func):
    """
    Decorator that allows free tier OR licensed access.

    Free tier: Ollama + tinyllama only
    Licensed: Any provider/model
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Always allow - actual restrictions checked per-request
        return func(*args, **kwargs)
    return wrapper


def requires_licensed_ai(func):
    """Decorator for features that always require a license"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not has_valid_license():
            return jsonify(
                ErrorResponse(
                    error='This feature requires a KillKrill license. Free tier supports Ollama with tinyllama model only.',
                    code='LICENSE_REQUIRED'
                ).model_dump()
            ), 403
        return func(*args, **kwargs)
    return wrapper


# =============================================================================
# Helper Functions
# =============================================================================


def get_provider_count() -> int:
    """Get current number of configured providers"""
    db = get_pydal_connection()
    return db(db.ai_providers.is_active == True).count()


def get_default_provider():
    """Get the default AI provider"""
    db = get_pydal_connection()
    provider = db(
        (db.ai_providers.is_default == True) &
        (db.ai_providers.is_active == True)
    ).select().first()

    if not provider:
        # Fall back to first active provider
        provider = db(db.ai_providers.is_active == True).select().first()

    return provider


def validate_provider_access(provider_type: str, model: str) -> tuple[bool, str]:
    """
    Validate if user can access the requested provider/model combination.

    Returns: (allowed, error_message)
    """
    # Check if it's a free tier request
    if is_free_tier_request(provider_type, model):
        # Check endpoint limit for free tier
        if not has_valid_license() and get_provider_count() >= FREE_TIER_MAX_ENDPOINTS:
            return False, f'Free tier limited to {FREE_TIER_MAX_ENDPOINTS} Ollama endpoint. Upgrade license for more.'
        return True, ''

    # Non-free tier requires license
    if not has_valid_license():
        if provider_type.lower() in LICENSED_PROVIDERS:
            return False, f'{provider_type.title()} requires a KillKrill license. Free tier supports Ollama with tinyllama only.'
        if model.lower() != FREE_TIER_MODEL:
            return False, f'Model "{model}" requires a license. Free tier supports tinyllama model only.'
        return False, 'This configuration requires a KillKrill license.'

    return True, ''


async def call_ollama(endpoint_url: str, model: str, prompt: str,
                      max_tokens: int, temperature: float, system_prompt: str = None) -> dict:
    """Call Ollama API for completion"""
    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {
            'num_predict': max_tokens,
            'temperature': temperature,
        }
    }

    if system_prompt:
        payload['system'] = system_prompt

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{endpoint_url.rstrip('/')}/api/generate",
            json=payload
        )
        response.raise_for_status()
        return response.json()


async def call_openai(api_key: str, model: str, prompt: str,
                      max_tokens: int, temperature: float, system_prompt: str = None) -> dict:
    """Call OpenAI API for completion"""
    messages = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': prompt})

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': temperature
            }
        )
        response.raise_for_status()
        return response.json()


async def call_claude(api_key: str, model: str, prompt: str,
                      max_tokens: int, temperature: float, system_prompt: str = None) -> dict:
    """Call Claude/Anthropic API for completion"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': model,
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': prompt}],
                'system': system_prompt or '',
                'temperature': temperature
            }
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# Provider Endpoints
# =============================================================================


@ai_analysis_bp.route('/providers', methods=['GET'])
@requires_ai_access
def list_providers():
    """
    GET: List configured AI providers.

    Free tier shows only Ollama providers with tinyllama.
    Licensed users see all providers.
    """
    db = get_pydal_connection()

    try:
        providers = db(db.ai_providers.is_active == True).select().as_list()

        # Filter for free tier users
        if not has_valid_license():
            providers = [
                p for p in providers
                if p['provider_type'] == FREE_TIER_PROVIDER and p['model'] == FREE_TIER_MODEL
            ]

        # Remove sensitive data
        for p in providers:
            if p.get('api_key'):
                p['api_key'] = '***' + p['api_key'][-4:] if len(p['api_key']) > 4 else '****'

        return jsonify(APIResponse(
            success=True,
            data={
                'providers': providers,
                'free_tier': not has_valid_license(),
                'free_tier_info': {
                    'provider': FREE_TIER_PROVIDER,
                    'model': FREE_TIER_MODEL,
                    'max_endpoints': FREE_TIER_MAX_ENDPOINTS
                } if not has_valid_license() else None
            }
        ).model_dump()), 200

    except Exception as e:
        logger.error(f"List providers error: {e}")
        return jsonify(
            ErrorResponse(error='Failed to list providers', code='SERVER_ERROR').model_dump()
        ), 500


@ai_analysis_bp.route('/providers', methods=['POST'])
@requires_ai_access
def create_provider():
    """
    POST: Create a new AI provider configuration.

    Free tier: Only Ollama with tinyllama, max 1 endpoint.
    Licensed: Any provider/model, unlimited endpoints.
    """
    db = get_pydal_connection()

    try:
        data = AIProviderCreate(**request.json)
    except ValidationError as e:
        return jsonify(ErrorResponse(error=str(e), code='VALIDATION_ERROR').model_dump()), 400

    try:
        # Validate access
        allowed, error_msg = validate_provider_access(data.provider_type, data.model)
        if not allowed:
            return jsonify(ErrorResponse(error=error_msg, code='LICENSE_REQUIRED').model_dump()), 403

        # Check endpoint limit for free tier
        if not has_valid_license():
            current_count = get_provider_count()
            if current_count >= FREE_TIER_MAX_ENDPOINTS:
                return jsonify(ErrorResponse(
                    error=f'Free tier limited to {FREE_TIER_MAX_ENDPOINTS} endpoint. Remove existing endpoint or upgrade license.',
                    code='LIMIT_EXCEEDED'
                ).model_dump()), 403

        # Require API key for licensed providers
        if data.provider_type in LICENSED_PROVIDERS and not data.api_key:
            return jsonify(ErrorResponse(
                error=f'API key required for {data.provider_type}',
                code='VALIDATION_ERROR'
            ).model_dump()), 400

        # If setting as default, unset other defaults
        if data.is_default:
            db(db.ai_providers.is_default == True).update(is_default=False)

        # Create provider
        provider_id = db.ai_providers.insert(
            name=data.name,
            provider_type=data.provider_type,
            endpoint_url=data.endpoint_url,
            api_key=data.api_key,
            model=data.model,
            is_default=data.is_default,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.commit()

        provider = db.ai_providers[provider_id].as_dict()
        if provider.get('api_key'):
            provider['api_key'] = '****'  # Mask for response

        logger.info(f"AI provider created: {data.name} ({data.provider_type})")
        return jsonify(APIResponse(success=True, data=provider).model_dump()), 201

    except Exception as e:
        logger.error(f"Create provider error: {e}")
        return jsonify(
            ErrorResponse(error='Failed to create provider', code='SERVER_ERROR').model_dump()
        ), 500


@ai_analysis_bp.route('/providers/<int:id>', methods=['GET'])
@requires_ai_access
def get_provider(id):
    """GET: Get provider by ID"""
    db = get_pydal_connection()

    try:
        provider = db.ai_providers[id]
        if not provider or not provider.is_active:
            return jsonify(ErrorResponse(error='Provider not found', code='NOT_FOUND').model_dump()), 404

        # Check access for free tier
        if not has_valid_license():
            if provider.provider_type != FREE_TIER_PROVIDER or provider.model != FREE_TIER_MODEL:
                return jsonify(ErrorResponse(
                    error='License required to access this provider',
                    code='LICENSE_REQUIRED'
                ).model_dump()), 403

        result = provider.as_dict()
        if result.get('api_key'):
            result['api_key'] = '****'

        return jsonify(APIResponse(success=True, data=result).model_dump()), 200

    except Exception as e:
        logger.error(f"Get provider error: {e}")
        return jsonify(ErrorResponse(error='Failed to get provider', code='SERVER_ERROR').model_dump()), 500


@ai_analysis_bp.route('/providers/<int:id>', methods=['DELETE'])
@requires_ai_access
def delete_provider(id):
    """DELETE: Remove a provider configuration"""
    db = get_pydal_connection()

    try:
        provider = db.ai_providers[id]
        if not provider:
            return jsonify(ErrorResponse(error='Provider not found', code='NOT_FOUND').model_dump()), 404

        # Soft delete
        db(db.ai_providers.id == id).update(is_active=False)
        db.commit()

        logger.info(f"AI provider deleted: {provider.name}")
        return jsonify(APIResponse(success=True, message='Provider deleted').model_dump()), 200

    except Exception as e:
        logger.error(f"Delete provider error: {e}")
        return jsonify(ErrorResponse(error='Failed to delete provider', code='SERVER_ERROR').model_dump()), 500


# =============================================================================
# Models Endpoint
# =============================================================================


@ai_analysis_bp.route('/models', methods=['GET'])
@requires_ai_access
def list_models():
    """
    GET: List available models.

    Free tier: Only tinyllama
    Licensed: All models from configured providers
    """
    db = get_pydal_connection()

    try:
        if not has_valid_license():
            # Free tier - only tinyllama
            return jsonify(APIResponse(
                success=True,
                data={
                    'models': [
                        {
                            'id': FREE_TIER_MODEL,
                            'name': 'TinyLlama',
                            'provider': FREE_TIER_PROVIDER,
                            'description': 'Lightweight LLM for basic analysis (free tier)',
                            'context_length': 2048,
                            'free_tier': True
                        }
                    ],
                    'license_required_for': ['gpt-4', 'gpt-3.5-turbo', 'claude-3-opus', 'claude-3-sonnet', 'llama2', 'mistral', 'etc.']
                }
            ).model_dump()), 200

        # Licensed - get models from all providers
        providers = db(db.ai_providers.is_active == True).select().as_list()

        models = []
        seen_models = set()

        for provider in providers:
            model_key = f"{provider['provider_type']}:{provider['model']}"
            if model_key not in seen_models:
                seen_models.add(model_key)
                models.append({
                    'id': provider['model'],
                    'name': provider['model'],
                    'provider': provider['provider_type'],
                    'provider_id': provider['id'],
                    'free_tier': is_free_tier_request(provider['provider_type'], provider['model'])
                })

        # Add common models for supported providers
        common_models = {
            'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
            'claude': ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
            'ollama': ['llama2', 'mistral', 'codellama', 'tinyllama']
        }

        return jsonify(APIResponse(
            success=True,
            data={
                'configured_models': models,
                'available_models': common_models
            }
        ).model_dump()), 200

    except Exception as e:
        logger.error(f"List models error: {e}")
        return jsonify(ErrorResponse(error='Failed to list models', code='SERVER_ERROR').model_dump()), 500


# =============================================================================
# Chat/Completion Endpoint
# =============================================================================


@ai_analysis_bp.route('/chat', methods=['POST'])
@requires_ai_access
def chat():
    """
    POST: Send a chat/completion request to configured AI provider.

    Free tier: Ollama + tinyllama only, max 2048 tokens
    Licensed: Any configured provider/model
    """
    db = get_pydal_connection()

    try:
        data = AIChatRequest(**request.json)
    except ValidationError as e:
        return jsonify(ErrorResponse(error=str(e), code='VALIDATION_ERROR').model_dump()), 400

    try:
        # Get provider
        if data.provider_id:
            provider = db.ai_providers[data.provider_id]
            if not provider or not provider.is_active:
                return jsonify(ErrorResponse(error='Provider not found', code='NOT_FOUND').model_dump()), 404
        else:
            provider = get_default_provider()
            if not provider:
                return jsonify(ErrorResponse(
                    error='No AI provider configured. Add a provider first.',
                    code='NO_PROVIDER'
                ).model_dump()), 400

        # Determine model to use
        model = data.model or provider.model

        # Validate access
        allowed, error_msg = validate_provider_access(provider.provider_type, model)
        if not allowed:
            return jsonify(ErrorResponse(error=error_msg, code='LICENSE_REQUIRED').model_dump()), 403

        # Enforce free tier token limit
        max_tokens = data.max_tokens
        if not has_valid_license():
            max_tokens = min(max_tokens, FREE_TIER_MAX_TOKENS)

        # Call appropriate provider (sync wrapper for async)
        import asyncio

        if provider.provider_type == 'ollama':
            result = asyncio.run(call_ollama(
                provider.endpoint_url, model, data.prompt,
                max_tokens, data.temperature, data.system_prompt
            ))
            response_text = result.get('response', '')
            usage = {
                'prompt_tokens': result.get('prompt_eval_count', 0),
                'completion_tokens': result.get('eval_count', 0),
                'total_tokens': result.get('prompt_eval_count', 0) + result.get('eval_count', 0)
            }

        elif provider.provider_type == 'openai':
            result = asyncio.run(call_openai(
                provider.api_key, model, data.prompt,
                max_tokens, data.temperature, data.system_prompt
            ))
            response_text = result['choices'][0]['message']['content']
            usage = result.get('usage', {})

        elif provider.provider_type == 'claude':
            result = asyncio.run(call_claude(
                provider.api_key, model, data.prompt,
                max_tokens, data.temperature, data.system_prompt
            ))
            response_text = result['content'][0]['text']
            usage = {
                'prompt_tokens': result.get('usage', {}).get('input_tokens', 0),
                'completion_tokens': result.get('usage', {}).get('output_tokens', 0),
                'total_tokens': result.get('usage', {}).get('input_tokens', 0) + result.get('usage', {}).get('output_tokens', 0)
            }
        else:
            return jsonify(ErrorResponse(
                error=f'Unsupported provider type: {provider.provider_type}',
                code='UNSUPPORTED_PROVIDER'
            ).model_dump()), 400

        return jsonify(APIResponse(
            success=True,
            data={
                'response': response_text,
                'model': model,
                'provider': provider.provider_type,
                'usage': usage,
                'free_tier': is_free_tier_request(provider.provider_type, model)
            }
        ).model_dump()), 200

    except httpx.HTTPStatusError as e:
        logger.error(f"AI provider HTTP error: {e}")
        return jsonify(ErrorResponse(
            error=f'AI provider error: {e.response.status_code}',
            code='PROVIDER_ERROR'
        ).model_dump()), 502
    except httpx.ConnectError as e:
        logger.error(f"AI provider connection error: {e}")
        return jsonify(ErrorResponse(
            error='Cannot connect to AI provider. Check endpoint URL.',
            code='CONNECTION_ERROR'
        ).model_dump()), 502
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify(ErrorResponse(error='Chat request failed', code='SERVER_ERROR').model_dump()), 500


# =============================================================================
# Analysis Endpoints
# =============================================================================


@ai_analysis_bp.route('/analyze', methods=['POST'])
@requires_ai_access
def analyze():
    """POST: Submit data for AI analysis using configured provider"""
    db = get_pydal_connection()

    try:
        data = AIAnalyzeRequest(**request.json)
    except ValidationError as e:
        return jsonify(ErrorResponse(error=str(e), code='VALIDATION_ERROR').model_dump()), 400

    try:
        # Get provider
        if data.provider_id:
            provider = db.ai_providers[data.provider_id]
        else:
            provider = get_default_provider()

        if not provider:
            return jsonify(ErrorResponse(
                error='No AI provider configured. Add a provider first.',
                code='NO_PROVIDER'
            ).model_dump()), 400

        # Validate access
        allowed, error_msg = validate_provider_access(provider.provider_type, provider.model)
        if not allowed:
            return jsonify(ErrorResponse(error=error_msg, code='LICENSE_REQUIRED').model_dump()), 403

        # Create analysis record
        analysis_id = db.ai_analyses.insert(
            analysis_type=data.analysis_type,
            input_data={'data_source': data.data_source, **data.input_data},
            result=None,
            status='pending',
            error_message=None,
            created_by=g.get('auth_context', {}).get('identity', 'anonymous'),
            created_at=datetime.utcnow(),
            completed_at=None
        )
        db.commit()

        analysis = db.ai_analyses[analysis_id].as_dict()
        return jsonify(APIResponse(success=True, data=analysis).model_dump()), 201

    except Exception as e:
        logger.error(f"Analysis creation error: {e}")
        return jsonify(ErrorResponse(error='Failed to create analysis', code='SERVER_ERROR').model_dump()), 500


@ai_analysis_bp.route('/results', methods=['GET'])
@requires_ai_access
def results_list():
    """GET: List all analysis results"""
    db = get_pydal_connection()

    try:
        limit = request.args.get('limit', 100, type=int)
        status = request.args.get('status', None)

        query = db.ai_analyses.id > 0
        if status:
            query &= (db.ai_analyses.status == status)

        results = db(query).select(
            limitby=(0, limit),
            orderby=~db.ai_analyses.created_at
        ).as_list()

        return jsonify(APIResponse(success=True, data={'results': results}).model_dump()), 200

    except Exception as e:
        logger.error(f"Results list error: {e}")
        return jsonify(ErrorResponse(error='Failed to list results', code='SERVER_ERROR').model_dump()), 500


@ai_analysis_bp.route('/results/<int:id>', methods=['GET'])
@requires_ai_access
def result_detail(id):
    """GET: Get analysis result by ID"""
    db = get_pydal_connection()

    try:
        analysis = db.ai_analyses[id]
        if not analysis:
            return jsonify(ErrorResponse(error='Analysis not found', code='NOT_FOUND').model_dump()), 404

        return jsonify(APIResponse(success=True, data=analysis.as_dict()).model_dump()), 200

    except Exception as e:
        logger.error(f"Result detail error: {e}")
        return jsonify(ErrorResponse(error='Failed to get result', code='SERVER_ERROR').model_dump()), 500


# =============================================================================
# Insights & Recommendations (Licensed Features)
# =============================================================================


@ai_analysis_bp.route('/insights', methods=['GET'])
@requires_licensed_ai
def get_insights():
    """GET: Get AI-generated insights (requires license)"""
    db = get_pydal_connection()

    try:
        limit = request.args.get('limit', 50, type=int)

        analyses = db(db.ai_analyses.status == 'completed').select(
            limitby=(0, limit),
            orderby=~db.ai_analyses.created_at
        ).as_list()

        insights = []
        for analysis in analyses:
            if analysis.get('result'):
                insights.append({
                    'id': analysis['id'],
                    'type': analysis['analysis_type'],
                    'insight': analysis['result'].get('summary', 'No summary'),
                    'confidence': analysis['result'].get('confidence', 0.0),
                    'created_at': analysis['created_at']
                })

        return jsonify(APIResponse(success=True, data={'insights': insights}).model_dump()), 200

    except Exception as e:
        logger.error(f"Insights error: {e}")
        return jsonify(ErrorResponse(error='Failed to get insights', code='SERVER_ERROR').model_dump()), 500


@ai_analysis_bp.route('/recommendations', methods=['GET'])
@requires_licensed_ai
def get_recommendations():
    """GET: Get AI-powered recommendations (requires license)"""
    db = get_pydal_connection()

    try:
        limit = request.args.get('limit', 10, type=int)

        analyses = db(db.ai_analyses.status == 'completed').select(
            limitby=(0, 100),
            orderby=~db.ai_analyses.created_at
        ).as_list()

        recommendations = []
        for analysis in analyses[:limit]:
            if analysis.get('result') and analysis['result'].get('recommendations'):
                rec = analysis['result']['recommendations']
                recommendations.append({
                    'id': analysis['id'],
                    'title': rec.get('title', 'Recommendation'),
                    'description': rec.get('description', ''),
                    'priority': rec.get('priority', 'medium'),
                    'created_at': analysis['created_at']
                })

        return jsonify(APIResponse(success=True, data={'recommendations': recommendations}).model_dump()), 200

    except Exception as e:
        logger.error(f"Recommendations error: {e}")
        return jsonify(ErrorResponse(error='Failed to get recommendations', code='SERVER_ERROR').model_dump()), 500


@ai_analysis_bp.route('/anomaly-detection', methods=['POST'])
@requires_licensed_ai
def detect_anomalies():
    """POST: Run anomaly detection (requires license)"""
    db = get_pydal_connection()

    try:
        data = request.json or {}

        if not data.get('metrics') or not isinstance(data.get('metrics'), list):
            return jsonify(ErrorResponse(
                error='metrics array is required',
                code='VALIDATION_ERROR'
            ).model_dump()), 400

        analysis_id = db.ai_analyses.insert(
            analysis_type='anomaly_detection',
            input_data={'metrics': data['metrics'], 'threshold': data.get('threshold', 2.0)},
            result=None,
            status='pending',
            error_message=None,
            created_by=g.get('auth_context', {}).get('identity', 'anonymous'),
            created_at=datetime.utcnow()
        )
        db.commit()

        analysis = db.ai_analyses[analysis_id].as_dict()
        return jsonify(APIResponse(success=True, data=analysis).model_dump()), 201

    except Exception as e:
        logger.error(f"Anomaly detection error: {e}")
        return jsonify(ErrorResponse(error='Failed to create anomaly detection', code='SERVER_ERROR').model_dump()), 500


# =============================================================================
# Config Endpoint
# =============================================================================


@ai_analysis_bp.route('/config', methods=['GET'])
@requires_ai_access
def get_config():
    """GET: Get AI analysis configuration and tier info"""
    try:
        licensed = has_valid_license()

        config = {
            'licensed': licensed,
            'tier': 'licensed' if licensed else 'free',
            'free_tier': {
                'provider': FREE_TIER_PROVIDER,
                'model': FREE_TIER_MODEL,
                'max_endpoints': FREE_TIER_MAX_ENDPOINTS,
                'max_tokens': FREE_TIER_MAX_TOKENS
            },
            'supported_providers': SUPPORTED_PROVIDERS if licensed else [FREE_TIER_PROVIDER],
            'features': {
                'chat': True,
                'analyze': True,
                'insights': licensed,
                'recommendations': licensed,
                'anomaly_detection': licensed,
                'multiple_endpoints': licensed,
                'custom_models': licensed
            },
            'timestamp': datetime.utcnow().isoformat()
        }

        return jsonify(APIResponse(success=True, data=config).model_dump()), 200

    except Exception as e:
        logger.error(f"Config error: {e}")
        return jsonify(ErrorResponse(error='Failed to get config', code='SERVER_ERROR').model_dump()), 500
