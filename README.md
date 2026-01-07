# AWS Marketplace Vendor Insights Setup

This repository provides tools and templates for deploying AWS Marketplace Vendor Insights to customer accounts. Vendor Insights lets AWS Marketplace sellers offer buyers on-demand access to security and compliance information for their SaaS solutions through a dashboard of 125 security controls.

## Setup Process Overview

The setup process consists of two main phases:

1. **Phase 1: Prepare Template URLs** - Get CloudFormation template URLs hosted in your S3 bucket
2. **Phase 2: Deploy CloudFormation Templates** - Use the URLs to deploy the actual Vendor Insights resources

## Quick Start

**Phase 1: Get Template URLs**
```bash
pip install -r requirements.txt
python3 setup_customer_templates.py --account-id 123456789012 --region us-west-2 --role-name Admin
```

**Phase 2: Deploy Templates**
Use the output URLs in CloudFormation (see [CloudFormation Deployment](#cloudformation-deployment) section)

## Overview

Vendor Insights evaluates security controls using four evidence sources:

1. **AWS Audit Manager & Config** - Automatically gathered evidence
2. **SOC2 Reports** - Shared directly with Vendor Insights  
3. **ISO Audit Reports** - Shared directly with Vendor Insights
4. **Self Assessment** - As few as 29 questions when other sources are enabled

The onboarding process deploys AWS services to collect evidence and build assessment reports using CloudFormation Stacks and StackSets.

## Files

- `setup_customer_templates.py` - Automated setup script
- `requirements.txt` - Python dependencies
- `v0/VendorInsightsPrerequisiteCFT.yaml` - IAM roles and StackSet permissions
- `v0/VendorInsightsOnboardingCFT.yaml` - Main Vendor Insights resources

## Prerequisites

1. Python 3.6 or later
2. AWS CLI configured with appropriate permissions
3. Access to assume roles in target customer accounts
4. Understanding of [AWS Marketplace Vendor Insights setup requirements](https://docs.aws.amazon.com/marketplace/latest/userguide/vendor-insights-setting-up.html)

## Phase 1: Prepare Template URLs

You can use either the automated script or manual steps to prepare your CloudFormation template URLs.

### Option A: Automated Script

#### Installation

```bash
pip install -r requirements.txt
```

#### Basic Usage

```bash
python3 setup_customer_templates.py --account-id 123456789012 --region us-west-2 --role-name Admin
```

#### Advanced Usage

```bash
python3 setup_customer_templates.py \
  --account-id 123456789012 \
  --region us-west-2 \
  --role-name Admin \
  --bucket-name my-custom-bucket
```

#### Parameters

- `--account-id` (required): Target AWS account ID
- `--region` (optional): AWS region (default: us-east-1)
- `--role-name` (optional): IAM role to assume (default: OrganizationAccountAccessRole)
- `--bucket-name` (optional): S3 bucket name (default: vendor-insights-templates-{account-id})

#### What the Script Does

1. Downloads the latest Vendor Insights templates from GitHub
2. Assumes the specified role in the target account
3. Creates an S3 bucket with versioning enabled
4. Updates template URLs to point to your bucket
5. Uploads all templates to S3
6. Outputs CloudFormation template URLs for deployment

### Option B: Manual Setup

#### Step 1: Download Templates

```bash
curl -L https://github.com/aws-samples/aws-marketplace-vendor-insights/archive/refs/heads/main.zip -o templates.zip
unzip templates.zip
cd aws-marketplace-vendor-insights-main/vendor-onboarding-templates
```

#### Step 2: Assume Role (if needed)

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/OrganizationAccountAccessRole \
  --role-session-name VendorInsightsSetup

# Export the credentials from the output:
export AWS_ACCESS_KEY_ID=<AccessKeyId>
export AWS_SECRET_ACCESS_KEY=<SecretAccessKey>
export AWS_SESSION_TOKEN=<SessionToken>
```

#### Step 3: Create S3 Bucket

```bash
aws s3 mb s3://vendor-insights-templates-123456789012 --region us-west-2
aws s3api put-bucket-versioning --bucket vendor-insights-templates-123456789012 --versioning-configuration Status=Enabled
```

#### Step 4: Update Template URLs

Replace all occurrences of:
```
https://aws-vendor-insights.s3.amazonaws.com/
```

With your bucket URL:
```
https://vendor-insights-templates-123456789012.s3.us-west-2.amazonaws.com/
```

#### Step 5: Upload Templates

```bash
aws s3 sync v0/ s3://vendor-insights-templates-123456789012/v0/ --region us-west-2
```

#### Step 6: Deploy CloudFormation Templates

Your template URLs will be:
- **Prerequisite**: `https://vendor-insights-templates-123456789012.s3.us-west-2.amazonaws.com/v0/VendorInsightsPrerequisiteCFT.yaml`
- **Onboarding**: `https://vendor-insights-templates-123456789012.s3.us-west-2.amazonaws.com/v0/VendorInsightsOnboardingCFT.yaml`

## Phase 2: Deploy CloudFormation Templates

Please refer to the [Setting up as a seller guide](https://docs.aws.amazon.com/marketplace/latest/userguide/vendor-insights-setting-up.html) for key onboarding steps. Onboarding steps (including prerequisites) include below.

* [AWS Audit Manager](https://docs.aws.amazon.com/audit-manager/latest/userguide/what-is.html):
    * The StackSet will create 2 Audit Manager assessments in AWS Audit Manager - a Self Assessment containing 125 controls and an Automated Assessment containing 30 controls. You can provide a buyer facing answer for each control in the Self Assessment while the Automated Assessment is automatically populated using AWS Config.
* [AWS Config](https://aws.amazon.com/config/): 
    * The StackSet will deploy an AWS Config [Conformance Pack](https://docs.aws.amazon.com/config/latest/developerguide/conformance-packs.html) to set up the requisite AWS Config rules that will allow the AWS Audit Manager automated assessment to gather live evidences for other AWS services deployed in that AWS account.
* [AWS S3](https://aws.amazon.com/s3/):
    * 3 S3 buckets with names *vendor-insights-stack-set-output-bucket-{account number},* *vendor-insights-audit-reports-bucket-{account number}* and *vendor-insights-assessment-reports-bucket-{account number}* will be created by the StackSet.
        * The bucket *vendor-insights-stack-set-output-bucket-{account number}* will contain outputs from the StackSet run that will be used by the Vendor Insights team to complete your onboarding and generate your Vendor Insights profile.
        * The bucket *vendor-insights-audit-reports-bucket-{account number}* will serve as a common link between your AWS account and the Vendor Insights service and will hold artifacts such as ISO-27001 and SOC2 certificates and reports that will be used as data sources by Vendor Insights.
        * AWS Audit Manager will [publish assessment reports](https://docs.aws.amazon.com/audit-manager/latest/userguide/assessment-reports.html) to the *vendor-insights-assessment-reports-bucket-{account number}* S3 bucket.
* [IAM](https://aws.amazon.com/iam/#:~:text=AWS%20Identity%20and%20Access%20Management%20(IAM)%20provides%20fine%2Dgrained,control%20across%20all%20of%20AWS.&text=IAM%20is%20a%20feature%20of,to%20the%20AWS%20Management%20Console.):
    * The StackSet will provision the following IAM roles in your account:
        * *AWSVendorInsightsRole* to which the Vendor Insights [Service Principal](https://docs.aws.amazon.com/IAM/latest/UserGuide/intro-structure.html#intro-structure-principal) will have access, in order to read the relevant information from the AWS Audit Manager resources and display them on your Vendor Insights profile.
        * *AWSVendorInsightsOnboardingDelegationRole* to which the Vendor Insights [Service Principal](https://docs.aws.amazon.com/IAM/latest/UserGuide/intro-structure.html#intro-structure-principal) will have access, in order to list and read the objects in *vendor-insights-audit-reports-bucket* and *vendor-insights-stack-set-output-bucket* buckets to complete the onboarding actions and generate your Vendor Insights profile.

The below guide covers the steps to be performed in order to deploy and configure the above mentioned resources required by Vendor Insights using [AWS CloudFormation](https://aws.amazon.com/cloudformation/) templates (CFT). 

**Note**: While [CFT StackSets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/what-is-cfnstacksets.html) support cross-account deployments, we recommend running these StackSets individually on each AWS account in which your AWS Marketplace SaaS product is running. In case your SaaS product is deployed to multiple regions within the account, all these regions should be provided to the StackSet when prompted, in order to ensure that AWS Config and AWS Audit Manager are correctly enabled for gathering evidences from all such regions.

## StackSet Execution Guide:

There are 2 CFT files that you will be running as part of the Vendor Insights setup. 

* *VendorInsightsPrerequisiteCFT.yaml* sets up the necessary admin role and execution permissions that are needed to run StackSets in your account. 
* *VendorInsightsOnboardingCFT.yaml* is responsible for setting up the above mentioned AWS services and configuring the appropriate IAM permissions that will allow Vendor Insights service to gather data for the SaaS product running in your AWS account and display those on your Vendor Insights profile. These template URLs are generated in Phase 1.

### **Step 1: Execute *VendorInsightsPrerequisiteCFT.yaml* to setup IAM permissions for the StackSet run:**

To begin the setup, execute the instructions to [Create a stack](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-using-console-create-stack-template.html) by specifying the S3 location for *VendorInsightsPrerequisiteCFT.yaml* (generated in Phase 1). You can provide a custom name for the Stack.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168182997-7ef27624-b6aa-4262-a8c7-32e214716029.png">

You may specify any additional tags you like for the resources deployed by this Stack. You can leave the *Stack failure option* to the default *“Roll back all stack resources”*.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183096-a1480f58-b772-48cb-b9b0-49341595a3fa.png">

On the final step, you will need to acknowledge the IAM role creation checkbox since this CFT run will provision the 2 IAM roles in your AWS account on completion - an *AdministratorRole* and *ExecutionRole* that will facilitate running the *VendorInsightsOnboardingCFT.yaml* StackSet in Step 2.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183109-bc99c4ed-b246-4258-b1f3-b2aab2941c2c.png">

Once the stack is successfully executed, you may proceed to **Step 2** below.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183119-2d3fc792-8c8c-420a-95da-44819396e65a.png">

### **Step 2: Execute *VendorInsightsOnboardingCFT.yaml* to setup AWS services for Vendor Insights:**

Next, execute the instructions to [Create a stack set with self-managed permissions](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-getting-started-create.html#stacksets-getting-started-create-self-managed). Select the *Self-service permissions* option. For the admin and execution permissions, use *AWSVendorInsightsOnboardingStackSetsAdmin* and *AWSVendorInsightsOnboardingStackSetsExecution* respectively that were previously created in Step 1.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183155-9fc54da7-352d-4139-b9d1-965ff734dbc6.png">

Specify the S3 location for *VendorInsightsOnboardingCFT.yaml* (generated in Phase 1).

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183189-49745610-56e7-4447-84d1-0b41d0a4ba10.png">

You can provide a name of your choice for the StackSet. For the StackSet parameters, enter the following values:

* **CreateVendorInsightsSelfAssessment**: This parameter sets up the Audit Manager self assessment in your AWS account. Leave this to the default value of True.
* **CreateVendorInsightsAutomatedAssessment**: This parameter sets up the Audit Manager automated assessment in your AWS account. Leave this to the default value of True.
* **CreateVendorInsightsBucket**: This parameter sets up an S3 bucket to facilitate the exchange of artifacts such as certificates and Audit Manager reports between the Vendor Insights service and you. Leave this to the default value of True.
* **CreateVendorInsightsIAMRoles**: This parameter provisions an IAM role that allows the Vendor Insights service to read the assessment and artifact data in your AWS account.
* **PrimaryRegion**: Set this parameter to the primary region for your SaaS deployment. This is the region where the S3 bucket and Self Assessment will be created in your AWS account. In case your SaaS product is deployed to just 1 region, then that region will be the primary region.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183233-6cbdfc53-9bf0-4c5c-8005-41f5a15a9278.png">

In the **Accounts** step of the StackSet execution, deploy the stack to the account you’re running the StackSet in by specifying the AWS account ID for the current account. ***Note***: While [CFT StackSets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/what-is-cfnstacksets.html) support cross-account deployments, we recommend running these StackSets individually on each AWS account in which your AWS Marketplace SaaS product is running.

On the **Specify region** step of the StackSet execution, provide a list of regions to which your SaaS product has been deployed. Automated Assessments will be created in each specified region. In case your SaaS product is deployed to just 1 region, then select just that region here. ***Note***: The first region in this list must be the region you set as your *PrimaryRegion* above.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183275-2a04d0cc-7722-493f-8ff5-ecbbdf6d7f37.png">

You can leave the *Region Concurrency* option to the default *Sequential* run.

On the final step, acknowledge both checkboxes before submission, since the additional IAM roles *AWSVendorInsightsRole* and *AWSVendorInsightsOnboardingDelegationRole* mentioned above will be created by this StackSet run.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183293-2eedb36a-9fe7-435f-8b4f-ea76b400b1e4.png">

Once the execution of the *VendorInsightsOnboardingCFT.yaml* StackSet is completed, you may begin uploading certification artifacts such as ISO-27001 and SOC2 reports to the *vendor-insights-audit-reports-bucket-{account number}* S3 bucket in your account.

<img width="422" alt="image" src="https://user-images.githubusercontent.com/3976999/168183312-5bb7063e-e049-4c34-9498-93f24f485077.png">

**Please contact AWS Marketplace** by replying to the welcome email invite you received, indicating that you’ve successfully run the StackSet in your account. The output files in *vendor-insights-stack-set-output-bucket-{account number}* will be used by the Vendor Insights support team to complete onboarding your product to Vendor Insights.

## **Contact us**

For any question or issues you may face when executing these steps, please visit the [AWS Marketplace seller support page](http://aws.amazon.com/marketplace/management/contact-us/?category=listing&details=Hello%20AWS%20Marketplace%20Operations%20Team%2C%0A%0AI%20want%20to%20add%20security%20profile%20for%20product%20id%3A%20%3CProductId%3E%0A%0AThanks&marketplace=commercial&subCategory=update).

## Post-Deployment Steps

1. **Upload Certificates**: Add ISO-27001 and SOC2 reports to the audit reports bucket
2. **Complete Self Assessment**: Answer questions in AWS Audit Manager
3. **Contact AWS Marketplace**: Reply to your welcome email confirming successful deployment

## Troubleshooting

### Permission Errors
- Verify AWS credentials have assume role permissions
- Check role exists with correct trust policy
- Ensure role has S3 and CloudFormation permissions

### Network Issues
- Check internet connectivity for GitHub downloads
- Corporate firewalls may block access - use manual setup

### S3 Bucket Issues
- Bucket names must be globally unique
- Verify region supports S3 bucket creation
- Check for naming conflicts

### Template Issues
- Validate YAML syntax after URL modifications
- Ensure S3 URLs match your region format

## Required IAM Permissions

### For Assumed Role
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:PutBucketVersioning", 
                "s3:PutObject",
                "cloudformation:*",
                "iam:CreateRole",
                "iam:AttachRolePolicy"
            ],
            "Resource": "*"
        }
    ]
}
```

### For Script Execution
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sts:AssumeRole",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

## Appendix

### IAM Roles created by onboarding CFTs

#### 1. Admin role

The VendorInsightsPrerequisiteCFT.yaml template when deployed creates an Admin role labelled *AWSVendorInsightsOnboardingStackSetsAdmin.* Because of the mechanics of how CloudFormation Stack Sets work, this Admin role is needed in order for the Stack Set to deploy the required stacks into multiple regions simultaneously.

The *AWSVendorInsightsOnboardingStackSetsAdmin* role being used by CloudFormation Stack Sets service assumes the *AWSVendorInsightsOnboardingStackSetsExecution* role to deploy the individual parent and nested stacks in every region mentioned in the Stack Set deployment.

#### 2. Execution role

In addition to the Admin role, the VendorInsightsPrerequisiteCFT.yaml template is responsible for creating an Execution role labelled *AWSVendorInsightsOnboardingStackSetsExecution.* As explained for the Admin role, this Execution role is assumed by the Admin role being used by the Stack Set to finally deploy the necessary parent and nested stacks which are a part of the Vendor Insights onboarding process.

It can be useful to think of the link between *AWSVendorInsightsOnboardingStackSetsAdmin and AWSVendorInsightsOnboardingStackSetsExecution* roles through the means of Admin role assuming the Execution role as the bridge which enables CloudFormation StackSet to create CloudFormation Stack instances.

More on these roles here : https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-prereqs-self-managed.html

### Costs

- **AWS Config**: $0.003 per configuration item per region
- **Audit Manager**: Included in AWS Config pricing
- **S3 Storage**: Standard S3 pricing for stored artifacts
- **Total**: Varies based on resource changes and regions

For detailed cost estimation, see:
- [AWS Config billing estimation guide](https://aws.amazon.com/blogs/mt/use-amazon-athena-and-aws-cloudtrail-to-estimate-billing-for-aws-config-rule-evaluations/)
- [Config items per month calculation](https://aws.amazon.com/premiumsupport/knowledge-center/retrieve-aws-config-items-per-month/) 




## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

