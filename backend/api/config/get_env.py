import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Access the variables
aws_bucket_name = os.getenv("AWS_BUCKET_NAME")
aws_object_name = os.getenv("AWS_OBJECT_NAME")
aws_region_name = os.getenv("AWS_REGION_NAME")
aws_expiry = os.getenv("AWS_EXPIRATION")
voyage_api_key = os.getenv("VOYAGE_API_KEY")
db_url = os.getenv("DB_URL")
db_url = os.getenv("DB_URL")
jina_api_key = os.getenv("JINA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

cloudfront_base_url = os.getenv("CLOUDFRONT_BASE_URL")
cloudfront_key_pair_id = os.getenv("CLOUDFRONT_KEY_PAIR_ID")
cloudfront_private_key = os.getenv("CLOUDFRONT_PRIVATE_KEY").replace("\\n", "\n")
cloudfront_url_expiration = int(
    os.getenv("CLOUDFRONT_URL_EXPIRATION", "3600")
)

cloudflare_acccount_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
cloudflare_api_token = os.getenv("CLOUDFLARE_API_TOKEN")


