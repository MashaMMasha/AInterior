query ?= "A lightful living room, small bedroom and tiny kitchen"
save_dir ?= "./scenes"

run: 
	uvicorn obllomov.main:app --reload
req:
	pipreqs --mode gt --force . 
generate:
	python generate.py --query $(query) --save-dir $(save_dir)
