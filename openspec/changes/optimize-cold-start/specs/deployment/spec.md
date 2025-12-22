## ADDED Requirements

### Requirement: Optional startup CPU boost
The deployment script SHALL support enabling Cloud Run startup CPU boost to improve cold start latency.

#### Scenario: Deploy with CPU boost
- **WHEN** the deploy script runs with CPU boost enabled
- **THEN** the Cloud Run service is deployed with startup CPU boost

### Requirement: Lean container image
The container image SHALL exclude unused system dependencies to minimize image size and cold start time.

#### Scenario: Build the container image
- **WHEN** the Docker image is built for deployment
- **THEN** unused system dependencies such as ffmpeg are not installed

### Requirement: Lazy initialization of external clients
The bot service SHALL lazily initialize external clients to reduce work during cold start.

#### Scenario: Handle the first request after scale-to-zero
- **WHEN** the service is starting from zero
- **THEN** external clients are created only when first needed
