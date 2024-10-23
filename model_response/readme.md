# Model response System

![Python Version](https://img.shields.io/badge/python-3.12-blue)

## 📚 Overview
This AWS Lambda function processes user queries by leveraging Salesforce data and generating intelligent responses using Amazon Bedrock. It also manages user sessions and conversation history using DynamoDB.

## Features

- Handles user queries, including validation and error handling.
- Securely retrieves Salesforce credentials from AWS Secrets Manager.
- Interacts with Amazon Bedrock to generate AI-based responses.
- Stores and updates conversation history in DynamoDB.
- Provides pre-typed prompts to guide user interaction.

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


## How it works

1. **Input**: The Lambda function expects an event containing a `user_query` and `session_id`.
2. **Process**:
   - The query is cleaned and validated.
   - Salesforce credentials are retrieved.
   - Amazon Bedrock generates a response based on the user query and conversation history.
   - The chat history is stored or updated in DynamoDB.
3. **Output**: The function returns a response containing the generated text and pre-typed prompts.

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
