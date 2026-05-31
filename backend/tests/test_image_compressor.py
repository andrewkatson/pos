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
    target_size_kb = 50

    monkeypatch.setenv('DEST_BUCKET', dest_bucket)
    monkeypatch.setenv('TARGET_SIZE_KB', str(target_size_kb))

    # Large image so compression loop must reduce it below target_size_kb
    img = Image.new('RGB', (2000, 2000), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=95)
    img_data = img_byte_arr.getvalue()

    mock_s3_client.get_object.return_value = {'Body': io.BytesIO(img_data)}

    result = lambda_handler(make_s3_event(source_bucket, source_key), None)

    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['message'] == 'Image compressed successfully'
    assert body['source'] == f"{source_bucket}/{source_key}"
    assert body['destination'] == f"{dest_bucket}/{source_key}"
    assert body['final_size_kb'] <= target_size_kb

    mock_s3_client.get_object.assert_called_once_with(Bucket=source_bucket, Key=source_key)
    mock_s3_client.put_object.assert_called_once()
    _, put_kwargs = mock_s3_client.put_object.call_args
    assert put_kwargs['Bucket'] == dest_bucket
    assert put_kwargs['Key'] == source_key
    assert put_kwargs['ContentType'] == 'image/jpeg'


def test_lambda_handler_skips_non_image(mock_s3_client, monkeypatch):
    monkeypatch.setenv('DEST_BUCKET', 'dest-bucket')

    result = lambda_handler(make_s3_event('source-bucket', 'document.pdf'), None)

    assert result['statusCode'] == 200
    assert result['body'] == 'Skipped non-image'
    mock_s3_client.get_object.assert_not_called()


def test_lambda_handler_missing_records_raises():
    with pytest.raises(KeyError, match='Records'):
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
    _, put_kwargs = mock_s3_client.put_object.call_args
    assert put_kwargs['Bucket'] == dest_bucket
    assert put_kwargs['Key'] == source_key
    assert put_kwargs['ContentType'] == 'image/jpeg'


def _make_jpeg_with_exif_orientation(width, height, orientation):
    """Return JPEG bytes for a width x height image with the given EXIF Orientation tag."""
    img = Image.new('RGB', (width, height), color='blue')
    exif = img.getexif()
    exif[0x0112] = orientation  # tag 274 = Orientation
    buf = io.BytesIO()
    img.save(buf, format='JPEG', exif=exif.tobytes())
    return buf.getvalue()


def test_lambda_handler_exif_orientation_applied(mock_s3_client, monkeypatch):
    """Images with EXIF Orientation must be transposed so the stored pixel layout is upright."""
    source_bucket = 'source-bucket'
    source_key = 'portrait.jpg'
    dest_bucket = 'dest-bucket'

    monkeypatch.setenv('DEST_BUCKET', dest_bucket)
    monkeypatch.setenv('TARGET_SIZE_KB', '500')

    # 10-wide x 20-tall image tagged as "rotate 90 CW" (orientation=8).
    # After transpose the stored image should be 20-wide x 10-tall.
    img_data = _make_jpeg_with_exif_orientation(width=10, height=20, orientation=8)
    mock_s3_client.get_object.return_value = {'Body': io.BytesIO(img_data)}

    result = lambda_handler(make_s3_event(source_bucket, source_key), None)

    assert result['statusCode'] == 200
    _, put_kwargs = mock_s3_client.put_object.call_args
    output_img = Image.open(put_kwargs['Body'])
    assert output_img.width == 20
    assert output_img.height == 10
