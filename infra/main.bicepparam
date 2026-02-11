using './main.bicep'

param baseName = 'aiworkflow'
param location = 'eastus2'
param containerImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest' // Placeholder - replaced during deployment
param azureOpenAIEndpoint = '' // Set via azd env or override at deploy time
param azureOpenAIDeploymentName = 'gpt-4o-mini'
param azureOpenAIApiVersion = '2024-12-01-preview'
