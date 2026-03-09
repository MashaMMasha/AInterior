run: 
	uvicorn obllomov.main:app --reload
req:
	pipreqs --mode gt --force . 
