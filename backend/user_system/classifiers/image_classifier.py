import os
import boto3
import logging
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse
from .classifier_constants import POSITIVE_IMAGE_FILENAME, IMAGE_CLASSIFIER_PROMPT
from .classifier_utils import (
    get_available_apis, classify_with_thresholds, ClassificationResult,
    IMAGE_API_DISPATCH,
)
from ..utils import convert_to_bool

logger = logging.getLogger(__name__)


def is_image_positive(image_url):
    _p = urlparse(image_url)
    logger.debug("is_image_positive called with URL: %s", _p._replace(query='', fragment='').geturl())
    testing = os.environ.get("TESTING", False)
    testing = testing if isinstance(testing, bool) else convert_to_bool(testing)

    if testing:
        parsed_url = urlparse(image_url)
        allowed = parsed_url.path.endswith(POSITIVE_IMAGE_FILENAME)
        logger.debug("Testing mode - path=%s endswith %s -> %s", parsed_url.path, POSITIVE_IMAGE_FILENAME, allowed)
        return ClassificationResult(allowed=allowed)

    logger.debug("Checking available AI APIs for image classification")
    available_apis = get_available_apis()
    logger.info("Available APIs for image classification: %s", available_apis)

    if not available_apis:
        logger.error("No AI API keys available.")
        return ClassificationResult(allowed=False)

    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key or not aws_secret_key:
        logger.error("Missing AWS credentials — AWS_ACCESS_KEY_ID present=%s, AWS_SECRET_ACCESS_KEY present=%s",
                     bool(aws_access_key), bool(aws_secret_key))
        return ClassificationResult(allowed=False)

    try:
        region = os.environ.get("AWS_REGION", "us-east-1")
        logger.debug("Creating S3 client in region: %s", region)
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region
        )

        bucket_name = os.environ.get("AWS_STORAGE_BUCKET_NAME")
        key = image_url

        parsed = urlparse(image_url)
        logger.debug("Parsing image URL — scheme=%s netloc=%s path=%s", parsed.scheme, parsed.netloc, parsed.path)

        if parsed.scheme == 's3':
            bucket_name = parsed.netloc
            key = parsed.path.lstrip('/')
            logger.debug("s3:// URL — bucket=%s key=%s", bucket_name, key)
        elif parsed.scheme in ['http', 'https'] and 's3' in parsed.netloc:
            parts = parsed.netloc.split('.')
            # Path-style hosts (s3.amazonaws.com, s3.<region>.amazonaws.com,
            # s3-<region>.amazonaws.com) carry the bucket as the first path
            # segment. A virtual-hosted bucket whose own name starts with "s3-"
            # (e.g. s3-my-bucket.s3.amazonaws.com) is NOT path-style — there the
            # second label is the literal "s3" and the path is already just the
            # key — so exclude it.
            is_path_style = (parts[0] == 's3' or parts[0].startswith('s3-')) and (len(parts) < 2 or parts[1] != 's3')
            if is_path_style:
                # Path-style: s3[.region].amazonaws.com/bucket/key
                # or dashed-region: s3-region.amazonaws.com/bucket/key
                path_parts = parsed.path.lstrip('/').split('/', 1)
                if not bucket_name and len(path_parts) >= 2:
                    bucket_name = path_parts[0]
                    key = path_parts[1]
                    logger.debug("Derived bucket/key from path-style URL — bucket=%s key=%s", bucket_name, key)
                elif len(path_parts) >= 2:
                    key = path_parts[1]
                    logger.debug("Using env-var bucket; extracted key from path-style URL: %s", key)
            else:
                # Virtual-hosted-style: bucket.s3[.region].amazonaws.com/key
                if not bucket_name:
                    bucket_name = parts[0]
                    logger.debug("Derived bucket from virtual-hosted URL host: %s", bucket_name)
                else:
                    logger.debug("Using env-var bucket name: %s", bucket_name)
                # Always extract key from path for virtual-hosted-style URLs
                key = parsed.path.lstrip('/')
                logger.debug("Extracted key from path: %s", key)
        else:
            logger.warning("Unrecognized URL scheme or non-S3 host — scheme=%s netloc=%s; will use key=%s as-is", parsed.scheme, parsed.netloc, key)

        if not bucket_name:
            logger.error("Could not determine S3 bucket name from URL=%s and AWS_STORAGE_BUCKET_NAME is unset", image_url)
            return ClassificationResult(allowed=False)

        logger.info("Fetching image from S3 — bucket=%s key=%s", bucket_name, key)
        response = s3.get_object(Bucket=bucket_name, Key=key)
        content_length = response.get('ContentLength', 'unknown')
        content_type = response.get('ContentType', 'unknown')
        logger.debug("S3 object fetched — ContentLength=%s ContentType=%s", content_length, content_type)
        image_data = response['Body'].read()
        image = Image.open(BytesIO(image_data))
        logger.debug("PIL image opened — size=%s mode=%s", image.size, image.mode)

        def call_api(api_name):
            try:
                api_func = IMAGE_API_DISPATCH.get(api_name)
                if not api_func:
                    logger.error("Unsupported API name: %s", api_name)
                    return None
                logger.debug("Calling %s API for image classification", api_name)
                score = api_func(image, IMAGE_CLASSIFIER_PROMPT)
                logger.debug("%s API returned: %s", api_name, score)
                return score
            except Exception:
                logger.exception("Error calling %s API for image classification", api_name)
                return None

        logger.info("Starting image classification cascade with APIs: %s", available_apis)
        result = classify_with_thresholds(available_apis, call_api)
        logger.info("Image classification result for key=%s: %s", key, result)
        return result

    except Exception:
        logger.exception("Error in image classifier for URL: %s", image_url)
        return ClassificationResult(allowed=False)
