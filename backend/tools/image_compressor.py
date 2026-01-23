import boto3
import io
from PIL import Image
import os

class ImageCompressor:
    def __init__(self, region_name='us-east-2'):
        self.s3 = boto3.client('s3', region_name=region_name)

    def compress_s3_image(self, source_bucket, source_key, dest_bucket, dest_key, target_size_kb=500):
        """
        Downloads an image from S3, compresses it to be under target_size_kb,
        and uploads it to a destination bucket.
        """
        # 1. Download image from S3
        response = self.s3.get_object(Bucket=source_bucket, Key=source_key)
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
        self.s3.put_object(
            Bucket=dest_bucket,
            Key=dest_key,
            Body=output_buffer,
            ContentType='image/jpeg'
        )
        
        print(f"Successfully compressed {source_key} to {size_kb:.2f}kb and uploaded to {dest_bucket}/{dest_key}")
        return dest_key

if __name__ == "__main__":
    # Example usage (would typically be triggered by an S3 event or Lambda)
    compressor = ImageCompressor()
    # compressor.compress_s3_image('goodvibesonly-images', 'input.jpg', 'goodvibesonly-compressed', 'output.jpg')
