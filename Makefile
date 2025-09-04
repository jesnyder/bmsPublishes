DEFAULT_GOAL:  web


# install requirements
.PHONY: getreqs
getreqs:
	sudo apt-get clean
	#sudo apt install texlive-latex-base
	pip install --upgrade -r reqs.txt


# analyze the dataset
.PHONY: pythonanalysis
pythonanalysis:
	python3  user_provided/python/main.py

#.PHONY: pdf
#pdf: pythonanalysis
#	cp code/latex/report.txt code/latex/report.tex
#	aspell check code/latex/*.tex
#	pdflatex -output-directory=latex code/latex/reportTEX.tex
#	cp code/latex/report.pdf report.pdf


# serve the local directory
.PHONY: web
web: pythonanalysis
	python3 -m http.server --directory docs/
	#python3 -mwebbrowser http://127.0.0.1:8000/report.pdf
