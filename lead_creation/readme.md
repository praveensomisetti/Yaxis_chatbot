# Lead Creation System

![Python Version](https://img.shields.io/badge/python-3.12-blue)

## 📚 Overview
The Lead Creation Lambda function processes a user's input during a chat session and determines whether to create a qualified lead in Salesforce. It interacts with AWS Bedrock for user detail extraction, uses AWS Secrets Manager for secure Salesforce credentials, and DynamoDB for session history and lead storage.


## Technology Stack

- **AWS Services**: DynamoDB, Secrets Manager, Amazon Bedrock
- **CRM**: Salesforce
- **Programming Language**: Python
- **Libraries**: 
  - `boto3` for AWS interactions
  - `salesforce_bulk` (or equivalent) for Salesforce API interactions
  - `json` for parsing responses
  - `logging` for logging and monitoring
  
## 📂 Project Structure

```
	└── 📁 batch_job_lead_update 
		├── 📄 .dockerignore 										# Specifies files and directories ignored by Docker. 
		├── 📄 .gitignore 											# Specifies files and directories ignored by Git. 
		├── 📄 dockerfile 											# Dockerfile for building the project container. 
		├── 📁 prompts 											
			├── 📄 extraction_instructions.txt                  		# User details extraction prompt.
			├── 📄 summary_instructions.txt                     		# Summary prompt based on conversations.	
			├── 📄 system_instructions.txt                      		# Yaxis bot system prompt
		├── 📄 lambda_function.py 									# Main logic for the AWS Lambda function. 
		├── 📄 logger_config.py 										# Configuration for logging. 
		├── 📄 readme.md 											# Project overview and setup instructions. 
		├── 📄 requirements.txt 										# List of dependencies required for the project. 
		├── 📄 utils.py												# Utility functions used throughout the project. │ 
		├── 📄 validate_user_details.py 								# Functions for validating user details.
```

## ⚙️ Prerequisites

- AWS credentials configured with access to DynamoDB, Secrets Manager, and Bedrock.
- Salesforce credentials stored in AWS Secrets Manager.
- Python 3.12 installed on your system.
- Salesforce API access for creating, updating, and managing lead data.

## Environment Setup

Before running the system, ensure that the following environment variables are set:

| Variable Name          | Description                                                       |
|------------------------|-------------------------------------------------------------------|
| `secret_name`           | AWS Secrets Manager secret that contains Salesforce credentials.  |
| `secret_region_name`    | AWS region where the secret is stored.                           |
| `model_id`              | ID of the Amazon Bedrock model used to extract user details.      |
| `chat_history_table`    | Name of the DynamoDB table containing chat history data.         |
| `leads_table_name`      | Name of the DynamoDB table storing leads information.            |
| `bedrock_region_name`   | AWS region where Bedrock is deployed.                            |
| `dynamodb_region_name`  | AWS region where DynamoDB is deployed.                           |
| `guardrail_id`          | Bedrock guardrail ID for data extraction.                        |
| `guardrail_version`     | Version of the Bedrock guardrail.                                |

## How It Works

1. The function receives a user query and session ID.
2. It cleans the user query and fetches Salesforce credentials from Secrets Manager.
3. It uses the Bedrock model to extract user details from the chat history.
4. The function checks if the user qualifies for lead creation based on the input.
5. If qualified, it creates a lead in Salesforce and logs the details in DynamoDB.

## Error Handling

The function handles errors related to:
- Empty or invalid user queries.
- Failed retrieval of Salesforce secrets.
- Issues with Bedrock or DynamoDB clients.
- Failure to generate a response after multiple attempts.

## Setup

1. Clone the repository to your local machine.
2. Configure your AWS credentials.
3. Deploy the Lambda function with the necessary environment variables set.

## Usage

To invoke the Lambda function, send a payload containing `user_query` and `session_id`. The function will process the input and return the lead creation status along with any relevant messages.

## License

This project is licensed under the MIT License.