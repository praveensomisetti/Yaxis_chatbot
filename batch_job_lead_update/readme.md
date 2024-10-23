# Batch Lead Update System

![Python Version](https://img.shields.io/badge/python-3.12-blue)

## 📚 Overview

The **Batch Lead Update System** is an automated solution designed to process session IDs from recent chat sessions. It extracts relevant user information and updates leads in Salesforce, ensuring that the latest user information is accurately reflected in the Salesforce CRM. This automation streamlines the lead management process, making it more efficient and up-to-date.

## Features

- **Automated Lead Updates**: Automatically retrieves recent chat history and updates leads in Salesforce with any new details.
- **User Information Extraction**: Utilizes Amazon Bedrock to extract user information from chat messages.
- **Conversation Summaries**: Generates summaries of chat interactions to store in Salesforce for easy reference.
- **Seamless Integration**: Integrates with AWS services (Secrets Manager, DynamoDB, Bedrock) and Salesforce for a fully automated lead update process.
- **Robust Error Handling**: Implements comprehensive error handling and logging to ensure fault tolerance and recoverability from failures.

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

1. **Salesforce Authentication**: 
   - The system retrieves Salesforce credentials from AWS Secrets Manager.
   - Creates an object for Salesforce interaction.

2. **Session Processing**: 
   - The system pulls the most recent sessions (within the last 48 hours) from the DynamoDB table.
   - For each session, it retrieves the chat history and processes it to extract relevant details.

3. **User Details Extraction**:
   - Using Amazon Bedrock, the system extracts user information from chat messages.
   - It checks if the new information differs from the previously stored details in Salesforce.

4. **Lead Update**:
   - If any changes are detected (new email, phone, or name), Salesforce is updated with this new data.
   - Additionally, a conversation summary is generated using Bedrock and stored in Salesforce.

5. **DynamoDB Update**:
   - The updated lead information is then stored in DynamoDB for future reference and auditing.

6. **Error Handling**:
   - Errors encountered during any of these steps (e.g., API failures, AWS service errors) are logged, and the system continues processing the next session.

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