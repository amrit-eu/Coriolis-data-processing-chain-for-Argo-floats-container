Decoder Bindings
================

This Python package exists to bind to the dockerised Coriolis Decoder.

## Prerequisites

Before running, the decoder image must be ready on your local machine.

Follow the steps below to do this:

* Go to: https://github.com/amrit-eu/Coriolis-data-processing-chain-for-Argo-floats-container/tree/python_bindings
* Clone it, and cd into the directory with bindings.Dockerfile
* Run: `docker build -f bindings.Dockerfile -t decoder_matlab_tool:latest . `
* This now gives you an image 'decoder_matlab_tool.

You now have the Decoder image on your local machine ready to go!

---

The docker compose creates an environment consisting of 3 containers

1. The Matlab runtime (pulled from Ifremer)
2. The Decoder (This should exist from the prerequisite step)
3. The Python app (Built with Docker compose with the code from this repo)

To get up and running, make sure you have a valid WMO and add it to the docker compose (in the Python command) - A working demo one to use with the files in the repo is 6902892.

Then run:

`docker-compose up -d --build`

Pulling the runtime for the first time takes a while, but once done, doesn't need to be done again. After the containers have started you can see the output logs and files in the 'output_files' directory, as well as the logs in the Python container log screen.

