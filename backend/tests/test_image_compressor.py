import pytest
from unittest.mock import MagicMock, patch
import io
import json
from PIL import Image
from tools.image_compressor import lambda_handler


def make_s3_event(bucket, key):
    return {
        'Records': [{
            's3': {
                'bucket': {'name': bucket},
                'object': {'key': key}
            }
        }]
    }


@pytest.fixture
def mock_s3_client():
    with patch('boto3.client') as mock_client:
        yield mock_client.return_value


def test_lambda_handler_success(mock_s3_client, monkeypatch):
    source_bucket = 'source-bucket'
    source_key = 'input.jpg'
    dest_bucket = 'dest-bucket'

    monkeypatch.setenv('DEST_BUCKET', dest_bucket)
    monkeypatch.setenv('TARGET_SIZE_KB', '500')

    img = Image.new('RGB', (1000, 1000), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_data = img_byte_arr.getvalue()

    mock_s3_client.get_object.return_value = {'Body': io.BytesIO(img_data)}

    result = lambda_handler(make_s3_event(source_bucket, source_key), None)

    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'Image compressed successfully'
    assert body['source'] == f"{source_bucket}/{source_key}"
    assert body['destination'] == f"{dest_bucket}/{source_key}"

    mock_s3_client.get_object.assert_called_once_with(Bucket=source_bucket, Key=source_key)
    mock_s3_client.put_object.assert_called_once()


def test_lambda_handler_skips_non_image(mock_s3_client, monkeypatch):
    monkeypatch.setenv('DEST_BUCKET', 'dest-bucket')

    result = lambda_handler(make_s3_event('source-bucket', 'document.pdf'), None)

    assert result['statusCode'] == 200
    assert result['body'] == 'Skipped non-image'
    mock_s3_client.get_object.assert_not_called()


def test_lambda_handler_missing_records_raises():
    with pytest.raises(Exception):
        lambda_handler({}, None)


def test_lambda_handler_non_rgb(mock_s3_client, monkeypatch):
    source_bucket = 'source-bucket'
    source_key = 'input.png'
    dest_bucket = 'dest-bucket'

    monkeypatch.setenv('DEST_BUCKET', dest_bucket)

    img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_data = img_byte_arr.getvalue()

    mock_s3_client.get_object.return_value = {'Body': io.BytesIO(img_data)}

    result = lambda_handler(make_s3_event(source_bucket, source_key), None)

    assert result['statusCode'] == 200
    mock_s3_client.put_object.assert_called_once()
    _, kwargs = mock_s3_client.put_object.call_args
    assert kwargs['ContentType'] == 'image/jpeg'
