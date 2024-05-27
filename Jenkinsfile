pipeline {
    agent any

    options{
        // Max number of build logs to keep and days to keep
        buildDiscarder(logRotator(numToKeepStr: '5', daysToKeepStr: '5'))
        // Enable timestamp at each job in the pipeline
        timestamps()
    }

    environment{
        registry = 'hoanglong2410/chatbot'
        registryCredential = 'dockerhub_id'  
        version = "2.0.0"    
    }

    stages {
        stage('Build'){
            steps {
                script{
                    echo 'Building image for deployment...'
                    dockerImage = docker.build registry + ":" + version
                    echo 'Pushing image to dockerhub..'
                    docker.withRegistry( '', registryCredential ) {
                        dockerImage.push()
                    }
                }
            }
        }
        stage('Deploy') {
            agent {
                kubernetes {
                    containerTemplate {
                        name 'helm' // Name of the container to be used for helm upgrade
                        image 'fullstackdatascience/jenkins-k8s:lts'// The image containing helm
                        imagePullPolicy 'Always' // Always pull image in case of using the same tag
                    }
                }
            }
            steps {
                script {
                    container('helm') {
                        sh("helm upgrade --install chatbot ./helm/model-serving --namespace model-serving")
                    }
                }
            }
        }
    }
}
