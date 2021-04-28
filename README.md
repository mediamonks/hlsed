# hlsed

This is a small server script that can modify properties of the existing HLS playlists on the fly for testing purposes.

## Requirements

- Python 2.7
- Flask

## Running locally

Assuming you have Python 2.7 already make sure Flask is installed:

	pip install flask

To run locally in debug mode use the following from the root of the project:

	FLASK_APP=./src/app.py python -m flask run -p 11000
	
Or just:

	./serve.sh

## Deployment

This is a Flask application, so check out possible deployment options at their website: https://flask.palletsprojects.com/en/1.1.x/deploying/

### Example

Since we are using this script only for testing, we simply run it on our server using `nohup` to prevent it from shutting down when our SSH session ends:

	nohup FLASK_APP=./src/app.py python -m flask run -p 11000 &

The nginx is set up on this server to proxy all incoming requests to this particular port by adding the following into the server context:

    location / {
		proxy_pass http://localhost:11000/ ;
		proxy_set_header	Host	$host;	
    }

---
