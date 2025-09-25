Python Bindings
---------------

The Python app is located under: decArgo_soft/soft/decoder_api


To run the decoder with its associated bindings, run the following steps.


1. Build the image: `docker build -f Dockerfile --target python-runtime -t  decoder_matlab_tool:latest .`

2. Run the containers: `docker compose -f .\docker-compose.yml up -d --build`

The logs and files are written to the area: decArgo_demo/output.

