OPTIONS=--name="TestApp" --onefile --windowed --noconsole

download:
	@echo "> Clonning for UniqueBible..."
	rm -rf UniqueBible
	git clone https://github.com/eliranwong/UniqueBible.git

	@echo "> Done"

build:
	@echo "> Building for UniqueBible..."
	cd UniqueBible && rm -rf build/
	cd UniqueBible && rm -rf dist/
	cp UniqueBibleApp.spec UniqueBible/
	cp stuff/unique-bible-config.py UniqueBible/config.py
	cp stuff/unique-bible-gui.py UniqueBible/gui.py
	cd UniqueBible && pyinstaller ${OPTIONS} UniqueBibleApp.spec

	@echo "> Done"

spec:
	@echo "> Creating spec..."
	pyi-makespec ${OPTIONS} main.py
	@echo "> Done"

run-unique-bible:
	@echo "> Running..."
	cd UniqueBible/dist && ./UniqueBibleApp

	@echo "> Done"