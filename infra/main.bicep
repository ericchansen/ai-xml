// Main Bicep template for AI Workflow Authoring Demo
// Deploys: Azure AI Foundry (OpenAI) + model deployment + Azure Container Apps

targetScope = 'resourceGroup'

@description('Base name for all resources')
param baseName string = 'aiworkflow'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Container image to deploy')
param containerImage string

@description('Azure OpenAI deployment name')
param azureOpenAIDeploymentName string = 'gpt-4o-mini'

@description('Azure OpenAI API version')
param azureOpenAIApiVersion string = '2024-12-01-preview'

@description('Underlying model name for the deployment')
param modelName string = 'gpt-4o-mini'

@description('Model version')
param modelVersion string = '2024-07-18'

@description('Model deployment capacity (thousands of tokens per minute)')
param modelCapacity int = 30

// Unique suffix for resources whose names must be globally unique but aren't
// adopted by name. The Foundry account (openAiName) is intentionally fixed so
// deployments reconcile the existing aiworkflowauth resource in place; note
// this makes openAiName subject to cross-tenant name collisions.
var uniqueSuffix = uniqueString(resourceGroup().id)
var openAiName = '${baseName}auth'
var containerAppName = '${baseName}-app-${uniqueSuffix}'
var containerEnvName = '${baseName}-env-${uniqueSuffix}'
var logAnalyticsName = '${baseName}-logs-${uniqueSuffix}'
var acrName = '${baseName}acr${uniqueSuffix}'

// Built-in role: Cognitive Services OpenAI User
var openAiUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
)

// Azure AI Foundry (Cognitive Services) account hosting the OpenAI models.
// Owned by IaC so deployments are reproducible and don't drift into duplicates.
resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: openAiName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAiName
    publicNetworkAccess: 'Enabled'
    // App authenticates via managed identity (DefaultAzureCredential); keys are disabled.
    disableLocalAuth: true
  }
}

// Model deployment consumed by the app.
resource gptDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: azureOpenAIDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

// Log Analytics Workspace for Container Apps
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Azure Container Registry for Docker images
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// Container App with Managed Identity
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: {
    'azd-service-name': 'app'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8501
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ai-workflow-app'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: openAi.properties.endpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
              value: azureOpenAIDeploymentName
            }
            {
              name: 'AZURE_OPENAI_API_VERSION'
              value: azureOpenAIApiVersion
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    gptDeployment
  ]
}

// Grant the Container App's managed identity access to the Foundry account.
// Replaces the former postprovision shell hook so RBAC is captured in IaC.
resource openAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, containerApp.id, openAiUserRoleId)
  scope: openAi
  properties: {
    roleDefinitionId: openAiUserRoleId
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output containerAppName string = containerApp.name
output containerAppPrincipalId string = containerApp.identity.principalId
output resourceGroupName string = resourceGroup().name
output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.properties.loginServer
output azureOpenAIEndpoint string = openAi.properties.endpoint
output azureOpenAIAccountName string = openAi.name
output AZURE_OPENAI_DEPLOYMENT_NAME string = azureOpenAIDeploymentName
