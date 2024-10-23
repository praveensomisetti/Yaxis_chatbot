# **Batch Lead Update System**

## **Overview**

The **Batch Lead Update System** is an automated solution that processes chat sessions, extracts relevant user information, and updates leads in Salesforce. The system retrieves recent chat history stored in Amazon DynamoDB, validates user information via Amazon Bedrock, and synchronizes updated details into Salesforce. This process ensures that the latest user information is reflected in Salesforce CRM, making the lead management process more efficient and up-to-date.

## **Features**

- **Automated Lead Updates**: Retrieve recent chat history and update leads in Salesforce with any new details.
- **User Information Extraction**: Uses Amazon Bedrock to extract user information like name, email, and phone from chat messages.
- **Conversation Summaries**: Generates summaries of chat interactions to store in Salesforce for easy reference.
- **Seamless Integration**: Integrates with AWS services (Secrets Manager, DynamoDB, Bedrock) and Salesforce for a fully automated lead update process.
- **Error Handling**: Robust error handling and logging to ensure that the process is fault-tolerant and recoverable from failures.

## **Technology Stack**

- **AWS Services**: DynamoDB, Secrets Manager, Amazon Bedrock
- **CRM**: Salesforce
- **Programming Language**: Python
- **Libraries**: 
  - `boto3` for AWS interactions
  - `salesforce_bulk` (or equivalent) for Salesforce API interactions
  - `json` for parsing responses
  - `logging` for logging and monitoring

## **Prerequisites**

- AWS credentials configured with access to DynamoDB, Secrets Manager, and Bedrock.
- Salesforce credentials stored in AWS Secrets Manager.
- Python 3.8 or higher installed on your system.
- Salesforce API access for creating, updating, and managing lead data.

## **Environment Setup**

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

## **How It Works**

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

## **Installation & Setup**

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd batch-lead-update-system
