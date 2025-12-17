"""
KillKrill Flask Backend - Fleet API Blueprint
Endpoints for Fleet server integration with license-gated features.
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
import requests
import os
import logging

from app.api.v1.schemas import APIResponse, ErrorResponse
from shared.licensing.python_client import requires_feature, FeatureNotAvailableError

logger = logging.getLogger(__name__)

fleet_bp = Blueprint('fleet', __name__)

# Fleet server configuration from environment
FLEET_SERVER_URL = os.getenv('FLEET_SERVER_URL', 'http://localhost:8412')
FLEET_API_TOKEN = os.getenv('FLEET_API_TOKEN', '')


def _proxy_request(method: str, endpoint: str, data=None, params=None):
    """
    Proxy request to Fleet server.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Fleet API endpoint
        data: Request body data
        params: Query parameters

    Returns:
        Tuple of (response_data, status_code, error_message)
    """
    url = f"{FLEET_SERVER_URL}/api/v1{endpoint}"
    headers = {
        'Authorization': f'Bearer {FLEET_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
        else:
            return None, 400, f"Unsupported HTTP method: {method}"

        response.raise_for_status()
        return response.json(), response.status_code, None

    except requests.exceptions.ConnectionError:
        logger.error(f"Failed to connect to Fleet server at {FLEET_SERVER_URL}")
        return None, 503, "Fleet server unavailable"
    except requests.exceptions.RequestException as e:
        logger.error(f"Fleet request failed: {e}")
        return None, 502, f"Fleet server error: {str(e)}"


# ============================================================================
# Status Endpoint
# ============================================================================

@fleet_bp.route('/status', methods=['GET'])
def fleet_status():
    """GET: Get Fleet server status and summary."""
    data, status_code, error = _proxy_request('GET', '/fleet')

    if error:
        return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

    summary = {
        'status': 'operational',
        'timestamp': datetime.utcnow().isoformat(),
        'fleet_server': data
    }

    return jsonify(APIResponse(success=True, data=summary).model_dump()), 200


# ============================================================================
# Hosts Endpoints
# ============================================================================

@fleet_bp.route('/hosts', methods=['GET'])
def list_hosts():
    """GET: List all Fleet hosts."""
    # Parse query parameters for filtering
    params = {}
    if request.args.get('status'):
        params['status'] = request.args.get('status')
    if request.args.get('query_id'):
        params['query_id'] = request.args.get('query_id')

    data, status_code, error = _proxy_request('GET', '/hosts', params=params)

    if error:
        return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

    return jsonify(APIResponse(success=True, data=data).model_dump()), 200


@fleet_bp.route('/hosts/<int:host_id>', methods=['GET'])
def get_host(host_id):
    """GET: Get specific host details."""
    data, status_code, error = _proxy_request('GET', f'/hosts/{host_id}')

    if error:
        return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

    if status_code == 404:
        return jsonify(ErrorResponse(error='Host not found', code='NOT_FOUND').model_dump()), 404

    return jsonify(APIResponse(success=True, data=data).model_dump()), 200


# ============================================================================
# Queries Endpoints
# ============================================================================

@fleet_bp.route('/queries', methods=['GET'])
def list_queries():
    """GET: List all Fleet queries."""
    params = {}
    if request.args.get('order_key'):
        params['order_key'] = request.args.get('order_key')
    if request.args.get('order_direction'):
        params['order_direction'] = request.args.get('order_direction')

    data, status_code, error = _proxy_request('GET', '/queries', params=params)

    if error:
        return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

    return jsonify(APIResponse(success=True, data=data).model_dump()), 200


@fleet_bp.route('/queries/run', methods=['POST'])
@requires_feature('fleet_query_execution')
def run_query():
    """POST: Execute a query on Fleet hosts (license-gated enterprise feature)."""
    try:
        payload = request.json

        # Validate required fields
        if not payload.get('query'):
            return jsonify(ErrorResponse(
                error='Missing required field: query',
                code='VALIDATION_ERROR'
            ).model_dump()), 400

        # Proxy to Fleet query execution endpoint
        data, status_code, error = _proxy_request('POST', '/queries/run', data=payload)

        if error:
            return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

        return jsonify(APIResponse(success=True, data=data).model_dump()), 202

    except FeatureNotAvailableError as e:
        logger.warning(f"Query execution blocked: {e}")
        return jsonify(ErrorResponse(
            error='Fleet query execution requires a professional+ license',
            code='FEATURE_NOT_AVAILABLE'
        ).model_dump()), 403
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        return jsonify(ErrorResponse(error=str(e), code='INTERNAL_ERROR').model_dump()), 500


# ============================================================================
# Policies Endpoint
# ============================================================================

@fleet_bp.route('/policies', methods=['GET'])
def list_policies():
    """GET: List all Fleet policies."""
    params = {}
    if request.args.get('order_key'):
        params['order_key'] = request.args.get('order_key')
    if request.args.get('order_direction'):
        params['order_direction'] = request.args.get('order_direction')

    data, status_code, error = _proxy_request('GET', '/policies', params=params)

    if error:
        return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

    return jsonify(APIResponse(success=True, data=data).model_dump()), 200


@fleet_bp.route('/hosts', methods=['POST'])
@requires_feature('fleet_management')
def register_host():
    """POST: Register a new host with Fleet (license-gated)."""
    try:
        payload = request.json

        # Validate required fields
        if not payload.get('hostname'):
            return jsonify(ErrorResponse(
                error='Missing required field: hostname',
                code='VALIDATION_ERROR'
            ).model_dump()), 400

        # Proxy to Fleet host registration
        data, status_code, error = _proxy_request('POST', '/hosts', data=payload)

        if error:
            return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

        return jsonify(APIResponse(success=True, data=data).model_dump()), 201

    except FeatureNotAvailableError as e:
        logger.warning(f"Host registration blocked: {e}")
        return jsonify(ErrorResponse(
            error='Fleet host registration requires a professional+ license',
            code='FEATURE_NOT_AVAILABLE'
        ).model_dump()), 403
    except Exception as e:
        logger.error(f"Host registration error: {e}")
        return jsonify(ErrorResponse(error=str(e), code='INTERNAL_ERROR').model_dump()), 500


@fleet_bp.route('/hosts/<int:host_id>', methods=['DELETE'])
@requires_feature('fleet_management')
def remove_host(host_id):
    """DELETE: Remove a host from Fleet (license-gated)."""
    try:
        data, status_code, error = _proxy_request('DELETE', f'/hosts/{host_id}')

        if error:
            return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

        if status_code == 404:
            return jsonify(ErrorResponse(error='Host not found', code='NOT_FOUND').model_dump()), 404

        return jsonify(APIResponse(success=True, data={'message': 'Host removed successfully'}).model_dump()), 200

    except FeatureNotAvailableError as e:
        logger.warning(f"Host removal blocked: {e}")
        return jsonify(ErrorResponse(
            error='Fleet host removal requires a professional+ license',
            code='FEATURE_NOT_AVAILABLE'
        ).model_dump()), 403
    except Exception as e:
        logger.error(f"Host removal error: {e}")
        return jsonify(ErrorResponse(error=str(e), code='INTERNAL_ERROR').model_dump()), 500


@fleet_bp.route('/queries', methods=['POST'])
@requires_feature('fleet_query_execution')
def create_query():
    """POST: Create a new saved query (license-gated)."""
    try:
        payload = request.json

        # Validate required fields
        if not payload.get('name') or not payload.get('query'):
            return jsonify(ErrorResponse(
                error='Missing required fields: name, query',
                code='VALIDATION_ERROR'
            ).model_dump()), 400

        # Proxy to Fleet query creation
        data, status_code, error = _proxy_request('POST', '/queries', data=payload)

        if error:
            return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

        return jsonify(APIResponse(success=True, data=data).model_dump()), 201

    except FeatureNotAvailableError as e:
        logger.warning(f"Query creation blocked: {e}")
        return jsonify(ErrorResponse(
            error='Fleet query creation requires a professional+ license',
            code='FEATURE_NOT_AVAILABLE'
        ).model_dump()), 403
    except Exception as e:
        logger.error(f"Query creation error: {e}")
        return jsonify(ErrorResponse(error=str(e), code='INTERNAL_ERROR').model_dump()), 500


@fleet_bp.route('/policies', methods=['POST'])
@requires_feature('fleet_management')
def create_policy():
    """POST: Create a new policy (license-gated)."""
    try:
        payload = request.json

        # Validate required fields
        if not payload.get('name') or not payload.get('query'):
            return jsonify(ErrorResponse(
                error='Missing required fields: name, query',
                code='VALIDATION_ERROR'
            ).model_dump()), 400

        # Proxy to Fleet policy creation
        data, status_code, error = _proxy_request('POST', '/policies', data=payload)

        if error:
            return jsonify(ErrorResponse(error=error, code='FLEET_ERROR').model_dump()), status_code

        return jsonify(APIResponse(success=True, data=data).model_dump()), 201

    except FeatureNotAvailableError as e:
        logger.warning(f"Policy creation blocked: {e}")
        return jsonify(ErrorResponse(
            error='Fleet policy creation requires a professional+ license',
            code='FEATURE_NOT_AVAILABLE'
        ).model_dump()), 403
    except Exception as e:
        logger.error(f"Policy creation error: {e}")
        return jsonify(ErrorResponse(error=str(e), code='INTERNAL_ERROR').model_dump()), 500
