from fastapi.testclient import TestClient

from services.solver_api.app.bootstrap import create_app


def test_publication_pages_are_public_and_do_not_embed_trackers() -> None:
    with TestClient(create_app()) as client:
        for path in ('/', '/privacy', '/support'):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('text/html')
            assert "default-src 'none'" in response.headers['content-security-policy']
            assert 'set-cookie' not in response.headers
            assert '<script' not in response.text
        privacy = client.get('/privacy').text
        assert 'Temporary uploaded files are deleted' in privacy
        assert 'DATASET_CAPTURE_ENABLED=0' in privacy
        assert 'Vercel' in privacy
        assert 'memory cache' in privacy
