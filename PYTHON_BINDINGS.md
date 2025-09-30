# Python decoder API

The Python app is located under: `decArgo_api/`

To run the decoder as an API, run the following steps.

1. Copy `.env.demo` as `.env` file to configure the decoder for the demonstration.

2. Run decoder demo with matlab runtime thanks to docker compose

   ```bash
   ./docker-decoder-api-linux.sh 6902892
   ```

3. Check next directory to see decoder outputs : `./decArgo_demo/output/api`
