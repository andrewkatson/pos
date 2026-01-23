import pytest
from unittest.mock import MagicMock, patch
import io
from PIL import Image
from tools.image_compressor import ImageCompressor

@pytest.fixture
def mock_s3():
    with patch('boto3.client') as mock_client:
        yield mock_client()

def test_compress_s3_image_success(mock_s3):
    # Setup
    source_bucket = 'source-bucket'
    source_key = 'input.jpg'
    dest_bucket = 'dest-bucket'
    dest_key = 'output.jpg'
    
    # Create a dummy image
    img = Image.new('RGB', (1000, 1000), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_data = img_byte_arr.getvalue()
    
    # Mock S3 response
    mock_s3.get_object.return_value = {
        'Body': io.BytesIO(img_data)
    }
    
    compressor = ImageCompressor()
    
    # Execute
    result = compressor.compress_s3_image(source_bucket, source_key, dest_bucket, dest_key, target_size_kb=50)
    
    # Assert
    assert result == dest_key
    mock_s3.get_object.assert_called_once_with(Bucket=source_bucket, Key=source_key)
    mock_s3.put_object.assert_called_once()
    
    # Check that the uploaded data is smaller than the input data (likely, due to compression)
    args, kwargs = mock_s3.put_object.call_args
    uploaded_body = kwargs['Body']
    uploaded_body.seek(0, io.SEEK_END)
    assert uploaded_body.tell() / 1024 <= 50

def test_compress_s3_image_non_rgb(mock_s3):
    # Setup - RGBA image
    source_bucket = 'source-bucket'
    source_key = 'input.png'
    dest_bucket = 'dest-bucket'
    dest_key = 'output.jpg'
    
    img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_data = img_byte_arr.getvalue()
    
    mock_s3.get_object.return_value = {
        'Body': io.BytesIO(img_data)
    }
    
    compressor = ImageCompressor()
    
    # Execute
    compressor.compress_s3_image(source_bucket, source_key, dest_bucket, dest_key)
    
    # Assert
    mock_s3.put_object.assert_called_once()
    args, kwargs = mock_s3.put_object.call_args
    assert kwargs['ContentType'] == 'image/jpeg'
