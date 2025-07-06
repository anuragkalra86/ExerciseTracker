# Requirement 2: S3 Analysis Functionality

## Overview
Backend application that automatically processes MP4 files uploaded to S3 bucket, performs analysis, and cleans up processed files.

## Key Constraints
- **Separate project**: Different from current motion recording project
- **Automatic processing**: No manual intervention required
- **Cleanup**: Delete S3 files after successful analysis
- **Reliable**: Handle failures gracefully with retry mechanisms

## Design Options Evaluated

### Option 1: S3 Event Notifications + SNS + SQS (Multiple) + Microservices ⭐ **RECOMMENDED**
**Implementation**: S3 bucket sends events to SNS topic, which fans out to multiple SQS queues, each feeding a different analysis microservice

**Pros:**
- Event-driven architecture (real-time processing)
- Fan-out pattern supports multiple analysis microservices
- Each microservice has its own queue and processing characteristics
- Highly reliable with built-in retry mechanisms per service
- Handles failures gracefully with individual dead letter queues
- Easy to add/remove analysis microservices
- Services are completely decoupled from each other
- Different retry policies and scaling per service

**Cons:**
- Requires AWS SNS and multiple SQS setup
- More complex than single-queue approach
- Additional AWS service costs (SNS + multiple SQS)

**Technical Details:**
- S3 bucket configured with event notifications to SNS topic
- SNS topic fans out to multiple SQS queues (one per microservice)
- Each analysis microservice polls its dedicated SQS queue
- Message contains S3 object details for processing
- Independent retry logic and dead letter queues per service

### Option 2: S3 Event Notifications + Lambda
**Implementation**: S3 directly triggers Lambda function for each uploaded file

**Pros:**
- Serverless architecture (no infrastructure management)
- Automatic scaling based on load
- Real-time processing
- Pay-per-execution model

**Cons:**
- Lambda execution time limits (15 minutes maximum)
- May not suit complex/long-running analysis
- Less control over execution environment
- Cold start delays

### Option 3: S3 Event Notifications + EventBridge + Multiple Microservices ⭐ **ALTERNATIVE**
**Implementation**: S3 events routed through EventBridge to multiple analysis microservices

**Pros:**
- Advanced routing capabilities with flexible rules
- Native support for multiple targets
- Rich event filtering and transformation
- Can route to Lambda, SQS, SNS, or direct service invocation
- Sophisticated routing logic (e.g., different file types → different services)
- Integration with many AWS services
- Built-in retry and dead letter queue support

**Cons:**
- More complex setup and configuration
- Higher cost than SNS fan-out
- May be overkill for simple fan-out scenarios
- More moving parts to manage

**When to Choose This:**
- Need complex routing rules (e.g., route based on file size, type, metadata)
- Want to integrate with other AWS services beyond SQS
- Need advanced event transformation capabilities

### Option 4: Polling-based
**Implementation**: Analysis service periodically checks S3 for new files

**Pros:**
- Simple to implement and understand
- No AWS service dependencies beyond S3
- Easy to debug and maintain

**Cons:**
- Inefficient resource usage
- Delayed processing (polling interval)
- Need to track processed files (metadata/database)
- Manual state management

## Recommended Architecture

```
S3 Bucket (with new MP4 files)
    ↓ (S3 Event Notifications)
SNS Topic
    ↓ (fan-out to multiple queues)
┌─────────────────────────────────────────────────────────────┐
│  SQS Queue 1     SQS Queue 2     SQS Queue 3     SQS Queue N │
│      ↓               ↓               ↓               ↓       │
│  Exercise Form   Rep Counter    Pose Analysis   [New Service]│
│  Microservice    Microservice   Microservice    Microservice │
└─────────────────────────────────────────────────────────────┘
    ↓ (after all analyses complete)
Delete S3 File (coordinated cleanup)
```

### Example Microservices:
- **Exercise Form Analysis**: Analyze proper form and technique
- **Rep Counter**: Count repetitions and sets
- **Pose Estimation**: Extract body pose and movement patterns
- **Movement Quality**: Assess movement quality and tempo
- **Comparison Engine**: Compare different analysis approaches

## Implementation Plan

### Components to Create:
1. **Multiple Analysis Microservices**: Separate projects for each analysis type
2. **SNS Topic**: AWS SNS topic for S3 event fan-out
3. **Multiple SQS Queues**: One SQS queue per microservice
4. **S3 Event Configuration**: S3 bucket event notifications to SNS
5. **Coordination Service**: Manages file cleanup after all analyses complete
6. **Database/Storage**: Store analysis results from all microservices
7. **Dead Letter Queues**: One per microservice for failed messages

### Key Features:
- **Fan-out Processing**: Each S3 file triggers multiple analysis workflows
- **Independent Scaling**: Each microservice can scale independently
- **Specialized Analysis**: Each service focuses on specific analysis goals
- **Coordinated Cleanup**: Ensures S3 file deletion only after all analyses complete
- **Error Handling**: Independent retry logic per microservice
- **Result Aggregation**: Combine results from multiple analyses
- **Service Registry**: Track active analysis microservices

## Technical Requirements

### AWS Setup:
- **S3 Bucket**: Configure event notifications to SNS topic
- **SNS Topic**: Fan-out topic for S3 events
- **Multiple SQS Queues**: Standard queues for each microservice
- **Multiple Dead Letter Queues**: One per microservice for failed messages
- **IAM Permissions**: S3 read/delete, SNS publish, SQS read/write permissions
- **SNS Subscriptions**: Configure SQS queues as SNS subscribers

### Dependencies:
- `boto3`: AWS SDK for Python
- `opencv-python`: Video processing
- `numpy`: Numerical operations
- `sqlalchemy`: Database operations (if storing results)
- Video analysis libraries (TensorFlow, PyTorch, etc.)

### Infrastructure:
- **Compute**: EC2 instance or containerized deployment
- **Database**: PostgreSQL/MySQL for storing analysis results
- **Monitoring**: CloudWatch for metrics and alerts
- **Storage**: S3 for processed results (if needed)

## Event Flow Details

### S3 Event Notification Format:
```json
{
  "Records": [
    {
      "eventName": "s3:ObjectCreated:Put",
      "s3": {
        "bucket": {
          "name": "exercise-tracker-videos"
        },
        "object": {
          "key": "clip_20231215_143022.mp4",
          "size": 5242880
        }
      }
    }
  ]
}
```

### Processing Workflow:
1. **S3 Event**: New MP4 file uploaded to S3
2. **SNS Fan-out**: SNS topic receives S3 event, sends to all subscribed SQS queues
3. **Multiple Processing**: Each microservice polls its dedicated SQS queue
4. **Parse Event**: Extract S3 bucket and object key from SQS message
5. **Download File**: Download MP4 from S3 (or stream process)
6. **Analyze Video**: Perform specialized analysis (form, reps, pose, etc.)
7. **Store Results**: Save analysis results to database with completion status
8. **Coordination Check**: Coordination service checks if all analyses complete
9. **Cleanup**: Delete S3 object only after ALL analyses succeed
10. **Acknowledge**: Delete SQS message from individual queues

### Coordinated Cleanup Strategy:
- **Analysis Tracking**: Database tracks completion status per microservice
- **Cleanup Trigger**: S3 deletion only when all expected analyses complete
- **Failure Handling**: If any analysis fails, keep S3 file for retry
- **Timeout**: Delete S3 file after maximum time even if some analyses fail

## Error Handling Strategy

### Retry Logic:
- **Transient Failures**: Retry with exponential backoff
- **Permanent Failures**: Move to dead letter queue
- **Partial Failures**: Rollback and retry entire process

### Failure Scenarios:
- **Network Issues**: Retry S3 operations
- **Analysis Failures**: Log error, move to DLQ
- **Database Failures**: Retry with backoff
- **S3 Delete Failures**: Log warning, continue processing

## Monitoring and Observability

### Metrics to Track:
- Processing time per video
- Success/failure rates
- Queue depth and message age
- S3 storage usage
- Analysis accuracy metrics

### Alerts:
- High failure rates
- Long processing times
- Queue backlog buildup
- Dead letter queue messages

## Deployment Strategy

### Application Deployment:
- **Containerized**: Docker container for easy deployment
- **Service**: Run as systemd service or Kubernetes deployment
- **Scaling**: Multiple worker instances for high throughput
- **Configuration**: Environment-based configuration

### AWS Resources:
- **Infrastructure as Code**: Terraform or CloudFormation
- **Permissions**: Least privilege IAM policies
- **Monitoring**: CloudWatch dashboards and alarms

## Adding New Analysis Microservices

### Steps to Add New Analysis:
1. **Create New SQS Queue**: Set up dedicated queue for new microservice
2. **Subscribe to SNS**: Add SQS queue as subscriber to existing SNS topic
3. **Deploy Microservice**: Deploy new analysis service that polls the queue
4. **Update Coordination**: Register new service in coordination system
5. **Configure Monitoring**: Add metrics and alerts for new service

### Benefits of This Architecture:
- **Easy Expansion**: Add new analyses without modifying existing services
- **A/B Testing**: Run multiple approaches simultaneously for comparison
- **Independent Development**: Teams can develop different analyses in parallel
- **Specialized Optimization**: Each service optimized for its specific analysis

## Success Metrics
- All S3 files processed by ALL registered microservices
- Low latency from upload to analysis completion
- Reliable error handling and recovery across all services
- Comprehensive logging and monitoring per microservice
- Coordinated cleanup of processed files
- Scalable architecture supporting multiple analysis types
- Easy addition of new analysis microservices 