def test_home_route(test_client):
    """Test the home route."""
    response = test_client.get('/')
    assert response.status_code == 200
    assert b'Essaked\xc3\xb8b' in response.data  # Check if 'Essakedøb' is in the response

def test_manifest_route(test_client):
    """Test the manifest.json route."""
    response = test_client.get('/manifest.json/somepath')
    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()
    assert data['name'] == 'Essakedøb'

def test_manifest_admin_route(test_client):
    """Test the admin manifest.json route."""
    response = test_client.get('/manifest.json/admin')
    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()
    assert data['start_url'] == '/admin_index'

def test_admin_route(test_client):
    """Test the admin_index route."""
    response = test_client.get('/admin_index')
    assert response.status_code == 200
    assert b'admin' in response.data  # Simple check to ensure admin page loads
