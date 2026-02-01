import pytest
from unittest.mock import MagicMock, patch
import io
import json
from PIL import Image
from tools.image_compressor import lambda_handler

@pytest.fixture
def mock_s3():
    with patch('boto3.client') as mock_client:
        yield mock_client()

def test_lambda_handler_success(mock_s3):
    # Setup
    source_bucket = 'source-bucket'
    source_key = 'input.jpg'
    dest_bucket = 'dest-bucket'
    dest_key = 'output.jpg'
    
    event = {
        'source_bucket': source_bucket,
        'source_key': source_key,
        'dest_bucket': dest_bucket,
        'dest_key': dest_key,
        'target_size_kb': 50
    }
    
    # Create a dummy image
    img = Image.new('RGB', (1000, 1000), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_data = img_byte_arr.getvalue()
    
    # Mock S3 response
    mock_s3.get_object.return_value = {
        'Body': io.BytesIO(img_data)
    }
    
    # Execute
    result = lambda_handler(event, None)
    
    # Assert
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'Image compressed successfully'
    assert body['source'] == f"{source_bucket}/{source_key}"
    assert body['destination'] == f"{dest_bucket}/{dest_key}"
    
    mock_s3.get_object.assert_called_once_with(Bucket=source_bucket, Key=source_key)
    mock_s3.put_object.assert_called_once()
    
    # Check that the uploaded data is smaller than the input data
    args, kwargs = mock_s3.put_object.call_args
    uploaded_body = kwargs['Body']
    uploaded_body.seek(0, io.SEEK_END)
    assert uploaded_body.tell() / 1024 <= 50

def test_lambda_handler_missing_params():
    event = {
        'source_bucket': 'bucket'
        # Missing other required params
    }
    
    result = lambda_handler(event, None)
    
    assert result['statusCode'] == 400
    body = json.loads(result['body'])
    assert 'Missing required parameters' in body['error']

def test_lambda_handler_non_rgb(mock_s3):
    # Setup - RGBA image
    source_bucket = 'source-bucket'
    source_key = 'input.png'
    dest_bucket = 'dest-bucket'
    dest_key = 'output.jpg'
    
    event = {
        'source_bucket': source_bucket,
        'source_key': source_key,
        'dest_bucket': dest_bucket,
        'dest_key': dest_key
    }
    
    img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_data = img_byte_arr.getvalue()
    
    mock_s3.get_object.return_value = {
        'Body': io.BytesIO(img_data)
    }
    
    # Execute
    result = lambda_handler(event, None)
    
    # Assert
    assert result['statusCode'] == 200
    mock_s3.put_object.assert_called_once()
    args, kwargs = mock_s3.put_object.call_args
    assert kwargs['ContentType'] == 'image/jpeg'
