import json
import boto3
import io
import os
from urllib.parse import unquote_plus
from PIL import Image, ImageOps

def lambda_handler(event, context):
    try:
        # Parse S3 trigger event
        record = event['Records'][0]['s3']
        source_bucket = record['bucket']['name']
        source_key = unquote_plus(record['object']['key'])
        
        dest_bucket = os.environ['DEST_BUCKET']
        dest_key = source_key
        target_size_kb = int(os.environ.get('TARGET_SIZE_KB', 500))

        # Skip non-image files
        if not source_key.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            print(f"Skipping non-image file: {source_key}")
            return {'statusCode': 200, 'body': 'Skipped non-image'}

        s3 = boto3.client('s3')

        print(f"Downloading {source_bucket}/{source_key}")
        response = s3.get_object(Bucket=source_bucket, Key=source_key)
        image_data = response['Body'].read()

        img = Image.open(io.BytesIO(image_data))
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        quality = 95
        output_buffer = io.BytesIO()
        size_kb = None

        while quality > 10:
            output_buffer.seek(0)
            output_buffer.truncate()
            img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
            size_kb = output_buffer.tell() / 1024
            if size_kb <= target_size_kb:
                break
            quality -= 5

        output_buffer.seek(0)
        s3.put_object(
            Bucket=dest_bucket,
            Key=dest_key,
            Body=output_buffer,
            ContentType='image/jpeg'
        )

        print(f"Compressed to {size_kb:.2f}KB at quality={quality} → {dest_bucket}/{dest_key}")

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
        raise  # Re-raise so Lambda marks the invocation as failed (visible in CloudWatch)