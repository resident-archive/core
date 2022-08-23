FROM public.ecr.aws/lambda/python:3.9

RUN bash -c 'echo -e ${LAMBDA_TASK_ROOT}'

# Copy function code
COPY . ${LAMBDA_TASK_ROOT}

# Install the function's dependencies using file requirements.txt
# from your project folder.

COPY requirements.txt  .

RUN yum install git gcc -y
RUN pip install -r requirements.txt -t ./env

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "main.handle" ]
