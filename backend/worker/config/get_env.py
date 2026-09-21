import os
from dotenv import load_dotenv

# NOTE: deliberate duplicate of backend/api/config/get_env.py.
# api/ and worker/ are independently deployable containers with no
# shared package, so each keeps its own copy of the env it needs.
load_dotenv()

db_url = os.getenv("DB_URL")
jina_api_key = os.getenv("JINA_API_KEY")
sqs_queue_url = os.getenv("SQS_QUEUE_URL")
cloudflare_acccount_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
cloudflare_api_token = os.getenv("CLOUDFLARE_API_TOKEN")

cluster = os.getenv("ECS_CLUSTER")
task_defination = os.getenv("ECS_TASK_DEFINITION")