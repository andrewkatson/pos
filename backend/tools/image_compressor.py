import json
import boto3
import io
from PIL import Image

def lambda_handler(event, context):
    """
    Lambda handler for S3 image compression
    
    Expected event format:
    {
        "source_bucket": "my-source-bucket",
        "source_key": "path/to/image.jpg",
        "dest_bucket": "my-dest-bucket",
        "dest_key": "path/to/compressed-image.jpg",
        "target_size_kb": 500,
        "region_name": "us-east-2"
    }
    """
    try:
        # Extract parameters from event
        source_bucket = event.get('source_bucket')
        source_key = event.get('source_key')
        dest_bucket = event.get('dest_bucket')
        dest_key = event.get('dest_key')
        target_size_kb = event.get('target_size_kb', 500)
        region_name = event.get('region_name', 'us-east-2')
        
        # Validate required parameters
        if not all([source_bucket, source_key, dest_bucket, dest_key]):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters: source_bucket, source_key, dest_bucket, dest_key'
                })
            }
        
        # Initialize S3 client
        s3 = boto3.client('s3', region_name=region_name)
        
        # 1. Download image from S3
        print(f"Downloading image from {source_bucket}/{source_key}")
        response = s3.get_object(Bucket=source_bucket, Key=source_key)
        image_data = response['Body'].read()
        
        # 2. Open image with Pillow
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary (e.g., RGBA or P to JPEG requirements)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 3. Iterative compression
        quality = 95
        output_buffer = io.BytesIO()
        
        while quality > 10:
            output_buffer.seek(0)
            output_buffer.truncate()
            img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
            
            size_kb = output_buffer.tell() / 1024
            if size_kb <= target_size_kb:
                break
            
            quality -= 5
        
        # 4. Upload to destination bucket
        output_buffer.seek(0)
        s3.put_object(
            Bucket=dest_bucket,
            Key=dest_key,
            Body=output_buffer,
            ContentType='image/jpeg'
        )
        
        print(f"Successfully compressed {source_key} to {size_kb:.2f}kb and uploaded to {dest_bucket}/{dest_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Image compressed successfully',
                'source': f"{source_bucket}/{source_key}",
                'destination': f"{dest_bucket}/{dest_key}",
                'final_size_kb': round(size_kb, 2),
                'final_quality': quality
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }