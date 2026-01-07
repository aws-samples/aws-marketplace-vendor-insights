#!/usr/bin/env python3

import sys
import boto3
import requests
import zipfile
import tempfile
import shutil
import re
import argparse
import time
import logging
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# Constants
GITHUB_REPO_URL = "https://github.com/aws-samples/aws-marketplace-vendor-insights/archive/refs/heads/main.zip"
REQUEST_TIMEOUT = 30  # seconds
USER_AGENT = 'AWS-Marketplace-Vendor-Insights-Setup-Script'
IP_ADDRESS_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')


class VendorInsightsError(Exception):
    """Base exception for vendor insights setup errors"""
    pass


class RoleAssumptionError(VendorInsightsError):
    """Exception raised when role assumption fails"""
    pass


class BucketCreationError(VendorInsightsError):
    """Exception raised when bucket creation fails"""
    pass


def _is_safe_path(path: str, base_path: str) -> bool:
    """Check if extraction path is safe (prevents zip slip attacks)"""
    abs_path = Path(base_path).joinpath(path).resolve()
    abs_base = Path(base_path).resolve()
    return str(abs_path).startswith(str(abs_base))


def download_templates() -> Tuple[str, str]:
    """Download templates from GitHub. Returns (templates_path, temp_dir)."""
    temp_dir = tempfile.mkdtemp()
    try:
        with requests.Session() as session:
            with tempfile.NamedTemporaryFile(delete=True, suffix='.zip') as tmp_file:
                response = session.get(
                    GITHUB_REPO_URL,
                    timeout=REQUEST_TIMEOUT,
                    headers={'User-Agent': USER_AGENT}
                )
                response.raise_for_status()
                tmp_file.write(response.content)
                tmp_file.flush()

                with zipfile.ZipFile(tmp_file.name, 'r') as zip_ref:
                    # Validate all paths before extraction to prevent zip slip
                    for member in zip_ref.infolist():
                        if not _is_safe_path(member.filename, temp_dir):
                            raise VendorInsightsError(f"Unsafe path in archive: {member.filename}")
                    zip_ref.extractall(temp_dir)

        templates_path = Path(temp_dir) / "aws-marketplace-vendor-insights-main" / "vendor-onboarding-templates"
        if not templates_path.exists():
            raise FileNotFoundError("vendor-onboarding-templates folder not found")

        return str(templates_path), temp_dir
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def assume_role(
    account_id: str,
    role_name: Optional[str] = "OrganizationAccountAccessRole",
    region: Optional[str] = "us-east-1"
) -> boto3.Session:
    """Assume role in customer account"""
    if not re.match(r'^\d{12}$', account_id):
        raise ValueError("Invalid AWS account ID")

    try:
        sts = boto3.client('sts')
        # Check if we're already in the target account
        current_identity = sts.get_caller_identity()
        current_account = current_identity['Account']
    except Exception as e:
        raise RoleAssumptionError(f"Failed to get current AWS identity. Check AWS credentials: {e}")

    if current_account == account_id:
        logging.info(f"Already in target account {account_id}, using current session")
        return boto3.Session(region_name=region)

    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    try:
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="VendorInsightsTemplateSetup"
        )
    except sts.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            raise RoleAssumptionError(f"Access denied when assuming role {role_arn}. Check permissions.")
        elif error_code == 'NoSuchEntity':
            raise RoleAssumptionError(f"Role {role_arn} does not exist.")
        else:
            raise RoleAssumptionError(f"Failed to assume role {role_arn}: {e}")

    credentials = response['Credentials']

    return boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )


def _validate_bucket_name(bucket_name: str) -> None:
    """Validate S3 bucket name according to AWS rules"""
    if not re.match(r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$', bucket_name):
        raise ValueError(
            f"Invalid bucket name '{bucket_name}'. Must be 3-63 characters, "
            "start/end with lowercase letter or number, and contain only "
            "lowercase letters, numbers, hyphens, and periods."
        )
    if '..' in bucket_name:
        raise ValueError(f"Invalid bucket name '{bucket_name}'. Cannot contain consecutive periods.")
    if IP_ADDRESS_PATTERN.match(bucket_name):
        raise ValueError(f"Invalid bucket name '{bucket_name}'. Cannot be formatted as an IP address.")


def create_s3_bucket(session: boto3.Session, bucket_name: str, region: str) -> str:
    """Create S3 bucket in customer account"""
    s3 = session.client('s3')

    try:
        if region == 'us-east-1':
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )

        # Enable versioning
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )

        logging.info(f"Created S3 bucket: {bucket_name}")
        return f"https://{bucket_name}.s3.{region}.amazonaws.com"

    except s3.exceptions.BucketAlreadyOwnedByYou:
        logging.info(f"Bucket {bucket_name} already exists")
        return f"https://{bucket_name}.s3.{region}.amazonaws.com"
    except s3.exceptions.BucketAlreadyExists:
        raise BucketCreationError(
            f"Bucket name '{bucket_name}' is already taken by another AWS account. "
            "Please choose a different bucket name using --bucket-name parameter."
        )
    except Exception as e:
        raise BucketCreationError(f"Failed to create bucket {bucket_name}: {e}")


def modify_template_urls(templates_path: Path, s3_base_url: str) -> None:
    """Modify TemplateURL references in YAML files"""
    if not s3_base_url or not s3_base_url.startswith('https://'):
        raise ValueError("Invalid S3 base URL")

    for yaml_file in templates_path.rglob("*.yaml"):
        try:
            with open(yaml_file, 'r+') as f:
                content = f.read()
                content = re.sub(
                    r'https://aws-vendor-insights\.s3\.amazonaws\.com/',
                    f'{s3_base_url}/',
                    content
                )
                f.seek(0)
                f.write(content)
                f.truncate()
            logging.info(f"Modified: {yaml_file.name}")
        except IOError as e:
            raise RuntimeError(f"Failed to modify {yaml_file}: {e}")


def upload_templates(session: boto3.Session, templates_path: str, bucket_name: str) -> None:
    """Upload templates to S3 bucket"""
    s3 = session.client('s3')
    templates_dir = Path(templates_path)

    def upload_file(file_path: Path) -> None:
        if not file_path.is_file():
            return
        s3_key = str(file_path.relative_to(templates_dir)).replace('\\', '/')
        for attempt in range(3):
            try:
                text_types = ['.yaml', '.yml', '.py', '.csv']
                content_type = 'text/plain' if file_path.suffix in text_types else 'binary/octet-stream'
                s3.upload_file(
                    str(file_path),
                    bucket_name,
                    s3_key,
                    ExtraArgs={'ContentType': content_type}
                )
                logging.info(f"Uploaded: {s3_key}")
                break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Failed to upload {s3_key}: {e}")
                time.sleep(1)

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(upload_file, templates_dir.rglob("*")))


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description='Setup Vendor Insights templates in customer account')
    parser.add_argument('--account-id', required=True, help='Customer AWS account ID')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--role-name', default='OrganizationAccountAccessRole', help='IAM role to assume')
    parser.add_argument('--bucket-name', help='S3 bucket name (default: vendor-insights-templates-{account-id})')

    args = parser.parse_args()

    # Set default bucket name
    if not args.bucket_name:
        args.bucket_name = f"vendor-insights-templates-{args.account_id}"
    else:
        # Ensure user-provided bucket name is valid (lowercase, no invalid chars)
        args.bucket_name = args.bucket_name.lower()

    # Validate bucket name
    _validate_bucket_name(args.bucket_name)

    temp_dir = None
    try:
        logging.info("1. Downloading templates from GitHub...")
        templates_path, temp_dir = download_templates()

        logging.info("2. Assuming role in customer account...")
        session = assume_role(args.account_id, args.role_name, args.region)

        logging.info("3. Creating S3 bucket...")
        s3_base_url = create_s3_bucket(session, args.bucket_name, args.region)

        logging.info("4. Modifying template URLs...")
        modify_template_urls(Path(templates_path), s3_base_url)

        logging.info("5. Uploading templates to S3...")
        upload_templates(session, templates_path, args.bucket_name)

        logging.info("✅ Setup complete!")
        logging.info(f"Onboarding template URL: {s3_base_url}/v0/VendorInsightsOnboardingCFT.yaml")
        logging.info(f"Prerequisite template URL: {s3_base_url}/v0/VendorInsightsPrerequisiteCFT.yaml")

    except Exception as e:
        logging.error(f"Setup failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup temp directory
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
