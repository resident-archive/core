to-spotify:
	cd functions/to-spotify && source ./env.sh && python3 main.py

setup-to-spotify:
	aws ecr create-repository --repository-name ra_to-spotify --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE --region eu-west-1

deploy-to-spotify:
	aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com
	docker build -t ra_to-spotify functions/to-spotify
	docker tag ra_to-spotify:latest ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/ra_to-spotify:latest
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/ra_to-spotify:latest