import os, sys, re, config, webbrowser, platform, subprocess, zipfile, requests
from PySide2.QtCore import QUrl, Qt, QEvent, QRegExp
from PySide2.QtGui import QIcon, QGuiApplication, QTextCursor
from PySide2.QtPrintSupport import QPrinter, QPrintDialog
from PySide2.QtWidgets import (QAction, QGridLayout, QInputDialog, QLineEdit, QMainWindow, QMessageBox, QPushButton, QToolBar, QWidget, QDialog, QFileDialog, QLabel, QFrame, QTextEdit, QProgressBar, QCheckBox, QTabWidget)
from PySide2.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PySide2.QtTextToSpeech import QTextToSpeech, QVoice
from TextCommandParser import TextCommandParser
from BibleVerseParser import BibleVerseParser
from BiblesSqlite import BiblesSqlite
from TextFileReader import TextFileReader
from NoteSqlite import NoteSqlite
from ThirdParty import Converter
from shutil import copyfile

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.mainHistoryPage = [False, False, False, False, False]
        self.studyHistoryPage = [False, False, False, False, False]
        self.lastLoadedCommand = {"main": None, "study": None}

        self.textCommandParser = TextCommandParser(self)

        self.setWindowTitle('Unique Bible App')

        appIconFile = os.path.join("htmlResources", "theText.png")
        appIcon = QIcon(appIconFile)
        QGuiApplication.setWindowIcon(appIcon)

        self.create_menu()
        self.setupToolBar()
        self.setAdditionalToolBar()
        self.setupBaseUrl()

        self.mainView = None
        self.studyView = None
        self.noteEditor = None
        self.centralWidget = CentralWidget(self)
        self.instantView = self.centralWidget.instantView
        self.instantPage = self.instantView.page()
        self.instantPage.titleChanged.connect(self.instantTextCommandChanged)
        self.setCentralWidget(self.centralWidget)
        self.setMainPage()
        self.setStudyPage()
        self.resizeParallel()
        self.resizeInstant()

        # variable to check if notes in editor been modified
        self.noteSaved = True

        # variables to work with dialog

        frameStyle = QFrame.Sunken | QFrame.Panel

        self.openFileNameLabel = QLabel()
        self.openFileNameLabel.setFrameStyle(frameStyle)

        self.openFilesPath = ""

        self.directoryLabel = QLabel()
        self.directoryLabel.setFrameStyle(frameStyle)

        # check if the current version is up-to-date
        self.checkLatestUpdate()

    def __del__(self):
        del self.textCommandParser

    def closeEvent(self, event):
        if self.noteEditor:
            if self.noteEditor.close():
                event.accept()
                qApp.quit()
            else:
                event.ignore()
        else:
            event.accept()
            qApp.quit()

    # check migration
    def checkMigration(self):
        if config.version >= 0.56:
            biblesSqlite = BiblesSqlite()
            biblesWithBothVersions = biblesSqlite.migratePlainFormattedBibles()
            if biblesWithBothVersions:
                initialMessage = ("Migration is needed.", "It looks like that all or some of your bible files are not up-to-date for running this version.  We are helping you to update those files.  It will take a while.  When it is finished, you will receive another message.")
                self.displayNotice(initialMessage)
                biblesSqlite.proceedMigration(biblesWithBothVersions)
                finishMessage = ("Migration is finished." , "Your bible files are updated. Enjoy!")
                self.displayNotice(finishMessage)
            del biblesSqlite

    def displayNotice(self, title_message):
        title, message = title_message
        reply = QMessageBox.information(self, title, message)

    # manage key capture
    def event(self, event):
        if event.type() == QEvent.KeyRelease and event.key() == Qt.Key_Tab:
            self.textCommandLineEdit.setFocus()
            return True
        elif event.type() == QEvent.KeyRelease and event.key() == Qt.Key_Escape:
            self.setNoToolBar()
            return True
        return QWidget.event(self, event)

    # manage main page
    def setMainPage(self):
        # main page changes as tab is changed.
        #print(self.mainView.currentIndex())
        self.mainPage = self.mainView.currentWidget().page()
        self.mainPage.titleChanged.connect(self.mainTextCommandChanged)
        self.mainPage.loadFinished.connect(self.finishMainViewLoading)
        self.mainPage.pdfPrintingFinished.connect(self.pdfPrintingFinishedAction)

    def setStudyPage(self):
        # study page changes as tab is changed.
        #print(self.studyView.currentIndex())
        self.studyPage = self.studyView.currentWidget().page()
        self.studyPage.titleChanged.connect(self.studyTextCommandChanged)
        self.studyPage.loadFinished.connect(self.finishStudyViewLoading)
        self.studyPage.pdfPrintingFinished.connect(self.pdfPrintingFinishedAction)

    # manage latest update
    def checkLatestUpdate(self):
        # change the following 2 files for major changes of version
        # main.py line 17
        # https://biblebento.com/UniqueBibleAppVersion.txt
        try:
            request = requests.get("https://biblebento.com/UniqueBibleAppVersion.txt", timeout=5)
            if request.status_code == 200:
                if float(request.text) > config.version:
                    self.promptUpdate(request.text)
        except:
            pass

    def promptUpdate(self, latestVersion):
        reply = QMessageBox.question(self, "Update is available ...",
                    "Update is available ...\n\nLatest version: {0}\nInstalled version: {1}\n\nDo you want to proceed the update?".format(latestVersion, config.version),
                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.updateUniqueBibleApp()

    def updateUniqueBibleApp(self):
        file = "https://github.com/eliranwong/UniqueBible/archive/master.zip"
        request = requests.get(file)
        if request.status_code == 200:
            currentName = os.getcwd()
            tempName = os.path.join(os.path.dirname(os.getcwd()), "UniqueBible-master")
            if not currentName == tempName:
                os.rename(currentName, tempName)
            filename = file.split("/")[-1]
            with open(filename, "wb") as content:
                content.write(request.content)
            if filename.endswith(".zip"):
                zip = zipfile.ZipFile(filename, "r")
                zip.extractall(os.path.dirname(os.getcwd()))
                zip.close()
                os.remove(filename)
            if not currentName == tempName:
                os.rename(tempName, currentName)
            self.mainPage.runJavaScript('alert("UniqueBible.app updated. You need to restart the app to apply the changes.")')
        else:
            self.mainPage.runJavaScript('alert("Failed to download the latest update. Please check your internet connection.")')

    # manage download helper
    def downloadHelper(self, databaseInfo):
        self.downloader = Downloader(self, databaseInfo)
        self.downloader.show()

    def moduleInstalled(self, file):
        self.downloader.close()
        self.mainPage.runJavaScript('alert("{0}{1}{0} was downloaded and installed successfully.")'.format("'", file))

    def moduleInstalledFailed(self, file):
        self.downloader.close()
        self.mainPage.runJavaScript('alert("Failed to download {0}{1}{0}. Please check your internet connection.")'.format("'", file))

    # setup interface
    def create_menu(self):

        menu1 = self.menuBar().addMenu("&UniqueBible.app")
        menu1.addAction(QAction("&Update", self, triggered=self.updateUniqueBibleApp))
        menu1.addSeparator()
        appIcon = QIcon(os.path.join("htmlResources", "theText.png"))
        quit_action = QAction(appIcon, "E&xit", self, shortcut = "Ctrl+Q", triggered=qApp.quit)
        menu1.addAction(quit_action)

        menu2 = self.menuBar().addMenu("&View")
        menu2.addAction(QAction("&Full Screen", self, triggered=self.fullsizeWindow))
        menu2.addAction(QAction("&Resize", self, triggered=self.twoThirdWindow))
        menu2.addSeparator()
        menu2.addAction(QAction("&Top Half", self, triggered=self.halfScreenHeight))
        menu2.addAction(QAction("&Left Half", self, triggered=self.halfScreenWidth))

        menu3 = self.menuBar().addMenu("&Display")
        menu3.addAction(QAction("&All Toolbars [Show / Hide]", self, shortcut = "Ctrl+J", triggered=self.setNoToolBar))
        menu3.addAction(QAction("&Single Toolbar [On / Off]", self, shortcut = "Ctrl+G", triggered=self.hideShowAdditionalToolBar))
        menu3.addSeparator()
        menu3.addAction(QAction("&Main Toolbar [Show / Hide]", self, triggered=self.hideShowMainToolBar))
        menu3.addAction(QAction("&Secondary Toolbar [Show / Hide]", self, triggered=self.hideShowSecondaryToolBar))
        menu3.addAction(QAction("&Left Toolbar [Show / Hide]", self, triggered=self.hideShowLeftToolBar))
        menu3.addAction(QAction("&Right Toolbar [Show / Hide]", self, triggered=self.hideShowRightToolBar))
        menu3.addSeparator()
        menu3.addAction(QAction("&Toolbar Icons [Full-size / Standard]", self, triggered=self.switchIconSize))
        menu3.addSeparator()
        menu3.addAction(QAction("&Landscape / Portrait Mode", self, shortcut = "Ctrl+L", triggered=self.switchLandscapeMode))
        menu3.addSeparator()
        menu3.addAction(QAction("Study Vie&w [Resize / Hide]", self, shortcut = "Ctrl+W", triggered=self.parallel))
        menu3.addAction(QAction("Bo&ttom View [Show / Hide]", self, shortcut = "Ctrl+T", triggered=self.instant))
        menu3.addSeparator()
        menu3.addAction(QAction("&Hovering feature [Enable / Disable]", self, shortcut = "Ctrl+=", triggered=self.enableInstantButtonClicked))
        menu3.addSeparator()
        menu3.addAction(QAction("&Larger Font", self, shortcut = "Ctrl++", triggered=self.largerFont))
        menu3.addAction(QAction("&Smaller Font", self, shortcut = "Ctrl+-", triggered=self.smallerFont))
        menu3.addSeparator()
        menu3.addAction(QAction("&Formatted / Plain Bibles", self, shortcut = "Ctrl+P", triggered=self.enableParagraphButtonClicked))
        menu3.addAction(QAction("&Add Sub-headings to Plain Bibles", self, triggered=self.enableSubheadingButtonClicked))

        menu8 = self.menuBar().addMenu("&History")
        menu8.addAction(QAction("&Main", self, shortcut = "Ctrl+'", triggered=self.mainHistoryButtonClicked))
        menu8.addAction(QAction("&Back", self, shortcut = "Ctrl+[", triggered=self.back))
        menu8.addAction(QAction("&Forward", self, shortcut = "Ctrl+]", triggered=self.forward))
        menu8.addSeparator()
        menu8.addAction(QAction("&Secondary", self, shortcut = 'Ctrl+"', triggered=self.studyHistoryButtonClicked))
        menu8.addAction(QAction("&Back", self, shortcut = "Ctrl+{", triggered=self.studyBack))
        menu8.addAction(QAction("&Forward", self, shortcut = "Ctrl+}", triggered=self.studyForward))

        menu4 = self.menuBar().addMenu("&Study")
        menu4.addAction(QAction("&Next Chapter", self, shortcut = 'Ctrl+>', triggered=self.nextMainChapter))
        menu4.addAction(QAction("&Previous Chapter", self, shortcut = 'Ctrl+<', triggered=self.previousMainChapter))
        menu4.addSeparator()
        menu4.addAction(QAction("Smar&t Indexes", self, shortcut = "Ctrl+.", triggered=self.runINDEX))
        menu4.addAction(QAction("Commentar&y", self, shortcut = "Ctrl+Y", triggered=self.runCOMMENTARY))
        menu4.addSeparator()
        menu4.addAction(QAction("&Translations", self, triggered=self.runTRANSLATION))
        menu4.addAction(QAction("&Discourse", self, triggered=self.runDISCOURSE))
        menu4.addAction(QAction("&Words", self, triggered=self.runWORDS))
        menu4.addAction(QAction("&TDW Combo", self, shortcut = "Ctrl+K", triggered=self.runCOMBO))
        menu4.addSeparator()
        menu4.addAction(QAction("C&ross References", self, shortcut = "Ctrl+R", triggered=self.runCROSSREFERENCE))
        menu4.addAction(QAction("TSK (&Enhanced)", self, shortcut = "Ctrl+E", triggered=self.runTSKE))
        menu4.addSeparator()
        menu4.addAction(QAction("&Compare All Versions", self, shortcut = "Ctrl+D", triggered=self.runCOMPARE))
        menu4.addAction(QAction("&Compare with ...", self, triggered=self.mainRefButtonClicked))
        menu4.addAction(QAction("&Parallel with ...", self, triggered=self.mainRefButtonClicked))
        menu4.addSeparator()

        menu5 = self.menuBar().addMenu("&Search")
        menu5.addAction(QAction("&Last Opened Bible on Main View", self, shortcut = "Ctrl+1", triggered=self.displaySearchBibleCommand))
        menu5.addAction(QAction("&Last Opened Bible on Study View", self, shortcut = "Ctrl+2", triggered=self.displaySearchStudyBibleCommand))
        menu5.addSeparator()
        menu5.addAction(QAction("&Last Opened Dictionary", self, shortcut = "Ctrl+3", triggered=self.searchCommandBibleDictionary))
        menu5.addAction(QAction("&Last Opened Encyclopedia", self, shortcut = "Ctrl+4", triggered=self.searchCommandBibleEncyclopedia))
        menu5.addAction(QAction("&Last Opened Book", self, shortcut = "Ctrl+5", triggered=self.displaySearchBookCommand))
        menu5.addSeparator()
        menu5.addAction(QAction("&Bible Charcters", self, shortcut = "Ctrl+6", triggered=self.searchCommandBibleCharacter))
        menu5.addAction(QAction("&Bible Names", self, shortcut = "Ctrl+7", triggered=self.searchCommandBibleName))
        menu5.addAction(QAction("&Bible Locations", self, shortcut = "Ctrl+8", triggered=self.searchCommandBibleLocation))
        menu5.addAction(QAction("&Bible Topics", self, shortcut = "Ctrl+9", triggered=self.searchCommandBibleTopic))
        menu5.addSeparator()
        menu5.addAction(QAction("&Hebrew / Greek Lexicons", self, shortcut = "Ctrl+0", triggered=self.searchCommandLexicon))
        menu5.addSeparator()
        menu5.addAction(QAction("&Third Party Dictionaries", self, triggered=self.searchCommandThirdPartyDictionary))

        menu6 = self.menuBar().addMenu("&Notes")
        menu6.addAction(QAction("&Note on Main Chapter", self, triggered=self.openMainChapterNote))
        menu6.addAction(QAction("&Note on Secondary Chapter", self, triggered=self.openStudyChapterNote))
        menu6.addAction(QAction("&Search Notes on Chapters", self, triggered=self.searchCommandChapterNote))
        menu6.addSeparator()
        menu6.addAction(QAction("&Note on Main Verse", self, triggered=self.openMainVerseNote))
        menu6.addAction(QAction("&Note on Secondary Verse", self, triggered=self.openStudyVerseNote))
        menu6.addAction(QAction("&Search Notes on Verses", self, triggered=self.searchCommandVerseNote))

        menu7 = self.menuBar().addMenu("&Topics")
        menu7.addAction(QAction("&Create a Topical Note", self, shortcut = "Ctrl+N", triggered=self.createNewNoteFile))
        menu7.addSeparator()
        menu7.addAction(QAction("&Open Note Files", self, triggered=self.openTextFileDialog))
        menu7.addAction(QAction("&Recent Files", self, triggered=self.openExternalFileHistory))
        menu7.addAction(QAction("&Read Last Opened File", self, triggered=self.externalFileButtonClicked))
        menu7.addAction(QAction("&Edit Last Opened File", self, triggered=self.editExternalFileButtonClicked))
        menu7.addSeparator()
        menu7.addAction(QAction("&Paste from Clipboard", self, shortcut = "Ctrl+^", triggered=self.pasteFromClipboard))

        menu9 = self.menuBar().addMenu("&Resources")
        menu9.addAction(QAction("&Install Formatted Bibles", self, triggered=self.installMarvelBibles))
        menu9.addAction(QAction("&Install Bible Commentaries", self, triggered=self.installMarvelCommentaries))
        menu9.addAction(QAction("&Install Marvel.bible Datasets", self, triggered=self.installMarvelDatasets))
        menu9.addSeparator()
        menu9.addAction(QAction("&Import BibleBento Plus Lexicons in a Folder", self, triggered=self.importBBPlusLexiconInAFolder))
        menu9.addAction(QAction("&Import BibleBento Plus Dictionaries in a Folder", self, triggered=self.importBBPlusDictionaryInAFolder))
        menu9.addSeparator()
        menu9.addAction(QAction("&Import 3rd Party Modules", self, triggered=self.importModules))
        menu9.addAction(QAction("&Import Supported 3rd Party Modules in a Folder", self, triggered=self.importModulesInFolder))
        menu9.addAction(QAction("&Import Settings", self, triggered=self.importSettingsDialog))
        menu9.addSeparator()
        menu9.addAction(QAction("&Tag References in a File", self, triggered=self.tagFile))
        menu9.addAction(QAction("&Tag References in Multiple Files", self, triggered=self.tagFiles))
        menu9.addAction(QAction("&Tag References in All Files of a Folder", self, triggered=self.tagFolder))

        menu10 = self.menuBar().addMenu("&Information")
        menu10.addAction(QAction("&BibleTools.app", self, triggered=self.openBibleTools))
        menu10.addAction(QAction("&UniqueBible.app", self, triggered=self.openUniqueBible))
        menu10.addAction(QAction("&Marvel.bible", self, triggered=self.openMarvelBible))
        menu10.addAction(QAction("&BibleBento.com", self, triggered=self.openBibleBento))
        menu10.addAction(QAction("&OpenGNT.com", self, triggered=self.openOpenGNT))
        menu10.addSeparator()
        menu10.addAction(QAction("&GitHub Repositories", self, triggered=self.openSource))
        menu10.addAction(QAction("&Unique Bible", self, triggered=self.openUniqueBibleSource))
        menu10.addAction(QAction("&Open Hebrew Bible", self, triggered=self.openHebrewBibleSource))
        menu10.addAction(QAction("&Open Greek New Testament", self, triggered=self.openOpenGNTSource))
        menu10.addSeparator()
        menu10.addAction(QAction("&Credits", self, triggered=self.openCredits))
        menu10.addSeparator()
        menu10.addAction(QAction("&Contact Eliran Wong", self, triggered=self.contactEliranWong))

    def setupToolBar(self):
        if config.toolBarIconFullSize:
            self.setupToolBarFullIconSize()
        else:
            self.setupToolBarStandardIconSize()

    def setupToolBarStandardIconSize(self):

        textButtonStyle = "QPushButton {background-color: #151B54; color: white;} QPushButton:hover {background-color: #333972;} QPushButton:pressed { background-color: #515790;}"

        self.firstToolBar = QToolBar()
        self.firstToolBar.setWindowTitle("Main Toolbar")
        self.firstToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(self.firstToolBar)

        self.mainTextMenuButton = QPushButton(self.verseReference("main")[0])
        self.mainTextMenuButton.setToolTip("Main View Bible Menu")
        self.mainTextMenuButton.setStyleSheet(textButtonStyle)
        self.mainTextMenuButton.clicked.connect(self.mainTextMenu)
        self.firstToolBar.addWidget(self.mainTextMenuButton)

        self.mainRefButton = QPushButton(self.verseReference("main")[1])
        self.mainRefButton.setToolTip("Main View Active Verse Features")
        self.mainRefButton.setStyleSheet(textButtonStyle)
        self.mainRefButton.clicked.connect(self.mainRefButtonClicked)
        self.firstToolBar.addWidget(self.mainRefButton)

        openChapterNoteButton = QPushButton()
        #openChapterNoteButton.setFixedSize(40, 40)
        #openChapterNoteButton.setBaseSize(70, 70)
        openChapterNoteButton.setToolTip("Main View Chapter Notes")
        openChapterNoteButtonFile = os.path.join("htmlResources", "noteChapter.png")
        openChapterNoteButton.setIcon(QIcon(openChapterNoteButtonFile))
        openChapterNoteButton.clicked.connect(self.openMainChapterNote)
        self.firstToolBar.addWidget(openChapterNoteButton)
        #t = self.firstToolBar.addAction(QIcon(openChapterNoteButtonFile), "Main View Chapter Notes", self.openMainChapterNote)
        #openChapterNoteButtonFile = os.path.join("htmlResources", "search.png")
        #t.setIcon(QIcon(openChapterNoteButtonFile))

        openVerseNoteButton = QPushButton()
        openVerseNoteButton.setToolTip("Main View Verse Notes")
        openVerseNoteButtonFile = os.path.join("htmlResources", "noteVerse.png")
        openVerseNoteButton.setIcon(QIcon(openVerseNoteButtonFile))
        openVerseNoteButton.clicked.connect(self.openMainVerseNote)
        self.firstToolBar.addWidget(openVerseNoteButton)

        searchBibleButton = QPushButton()
        searchBibleButton.setToolTip("Search Last Opened Bible on Main View")
        searchBibleButtonFile = os.path.join("htmlResources", "search.png")
        searchBibleButton.setIcon(QIcon(searchBibleButtonFile))
        searchBibleButton.clicked.connect(self.displaySearchBibleCommand)
        self.firstToolBar.addWidget(searchBibleButton)

        searchBibleButton = QPushButton()
        searchBibleButton.setToolTip("Search Last Opened Bible on Main View with {0}".format(config.iSearchVersion))
        searchBibleButtonFile = os.path.join("htmlResources", "search_plus.png")
        searchBibleButton.setIcon(QIcon(searchBibleButtonFile))
        searchBibleButton.clicked.connect(self.displayISearchBibleCommand)
        self.firstToolBar.addWidget(searchBibleButton)

        self.firstToolBar.addSeparator()

        self.textCommandLineEdit = QLineEdit()
        self.textCommandLineEdit.setToolTip("Command Line")
        self.textCommandLineEdit.setMinimumWidth(100)
        self.textCommandLineEdit.returnPressed.connect(self.textCommandEntered)
        self.firstToolBar.addWidget(self.textCommandLineEdit)

        self.firstToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Show / Hide Other Toolbars")
        actionButtonFile = os.path.join("htmlResources", "toolbar.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.hideShowAdditionalToolBar)
        self.firstToolBar.addWidget(actionButton)

        self.addToolBarBreak()

        self.studyBibleToolBar = QToolBar()
        self.studyBibleToolBar.setWindowTitle("Bible on Study View")
        self.studyBibleToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(self.studyBibleToolBar)

        self.studyTextMenuButton = QPushButton(self.verseReference("study")[0])
        self.studyTextMenuButton.setToolTip("Study View Bible Menu")
        self.studyTextMenuButton.setStyleSheet(textButtonStyle)
        self.studyTextMenuButton.clicked.connect(self.studyTextMenu)
        self.studyBibleToolBar.addWidget(self.studyTextMenuButton)

        self.studyRefButton = QPushButton(self.verseReference("study")[1])
        self.studyRefButton.setToolTip("Study View Active Verse Features")
        self.studyRefButton.setStyleSheet(textButtonStyle)
        self.studyRefButton.clicked.connect(self.studyRefButtonClicked)
        self.studyBibleToolBar.addWidget(self.studyRefButton)

        openStudyChapterNoteButton = QPushButton()
        openStudyChapterNoteButton.setToolTip("Study View Chapter Notes")
        openStudyChapterNoteButtonFile = os.path.join("htmlResources", "noteChapter.png")
        openStudyChapterNoteButton.setIcon(QIcon(openStudyChapterNoteButtonFile))
        openStudyChapterNoteButton.clicked.connect(self.openStudyChapterNote)
        self.studyBibleToolBar.addWidget(openStudyChapterNoteButton)

        openStudyVerseNoteButton = QPushButton()
        openStudyVerseNoteButton.setToolTip("Study View Verse Notes")
        openStudyVerseNoteButtonFile = os.path.join("htmlResources", "noteVerse.png")
        openStudyVerseNoteButton.setIcon(QIcon(openStudyVerseNoteButtonFile))
        openStudyVerseNoteButton.clicked.connect(self.openStudyVerseNote)
        self.studyBibleToolBar.addWidget(openStudyVerseNoteButton)

        searchStudyBibleButton = QPushButton()
        searchStudyBibleButton.setToolTip("Search Last Opened Bible on Study View")
        searchStudyBibleButtonFile = os.path.join("htmlResources", "search.png")
        searchStudyBibleButton.setIcon(QIcon(searchStudyBibleButtonFile))
        searchStudyBibleButton.clicked.connect(self.displaySearchStudyBibleCommand)
        self.studyBibleToolBar.addWidget(searchStudyBibleButton)

        searchStudyBibleButton = QPushButton()
        searchStudyBibleButton.setToolTip("Search Last Opened Bible on Study View with {0}".format(config.iSearchVersion))
        searchStudyBibleButtonFile = os.path.join("htmlResources", "search_plus.png")
        searchStudyBibleButton.setIcon(QIcon(searchStudyBibleButtonFile))
        searchStudyBibleButton.clicked.connect(self.displayISearchStudyBibleCommand)
        self.studyBibleToolBar.addWidget(searchStudyBibleButton)

        self.secondToolBar = QToolBar()
        self.secondToolBar.setWindowTitle("Secondary Toolbar")
        self.secondToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(self.secondToolBar)

        self.enableStudyBibleButton = QPushButton()
        self.enableStudyBibleButton.setToolTip(self.getStudyBibleDisplayToolTip())
        enableStudyBibleButtonFile = os.path.join("htmlResources", self.getStudyBibleDisplay())
        self.enableStudyBibleButton.setIcon(QIcon(enableStudyBibleButtonFile))
        self.enableStudyBibleButton.clicked.connect(self.enableStudyBibleButtonClicked)
        self.secondToolBar.addWidget(self.enableStudyBibleButton)

        self.secondToolBar.addSeparator()

        self.commentaryRefButton = QPushButton(self.verseReference("commentary"))
        self.commentaryRefButton.setToolTip("Commentary Menu")
        self.commentaryRefButton.setStyleSheet(textButtonStyle)
        self.commentaryRefButton.clicked.connect(self.commentaryRefButtonClicked)
        self.secondToolBar.addWidget(self.commentaryRefButton)

        self.secondToolBar.addSeparator()

        self.bookButton = QPushButton(config.book)
        self.bookButton.setToolTip("Books")
        self.bookButton.setStyleSheet(textButtonStyle)
        self.bookButton.clicked.connect(self.openBookMenu)
        self.secondToolBar.addWidget(self.bookButton)

#        searchBookButton = QPushButton()
#        searchBookButton.setToolTip("Search Books")
#        searchBookButtonFile = os.path.join("htmlResources", "search.png")
#        searchBookButton.setIcon(QIcon(searchBookButtonFile))
#        searchBookButton.clicked.connect(self.displaySearchBookCommand)
#        self.secondToolBar.addWidget(searchBookButton)

        self.secondToolBar.addSeparator()

        newFileButton = QPushButton()
        newFileButton.setToolTip("Create a Topical Note")
        newFileButtonFile = os.path.join("htmlResources", "newfile.png")
        newFileButton.setIcon(QIcon(newFileButtonFile))
        newFileButton.clicked.connect(self.createNewNoteFile)
        self.secondToolBar.addWidget(newFileButton)

        openFileButton = QPushButton()
        openFileButton.setToolTip("Open Topical Notes")
        openFileButtonFile = os.path.join("htmlResources", "open.png")
        openFileButton.setIcon(QIcon(openFileButtonFile))
        openFileButton.clicked.connect(self.openTextFileDialog)
        self.secondToolBar.addWidget(openFileButton)

        self.externalFileButton = QPushButton(self.getLastExternalFileName())
        self.externalFileButton.setToolTip("Read Topical Notes")
        self.externalFileButton.setStyleSheet(textButtonStyle)
        self.externalFileButton.clicked.connect(self.externalFileButtonClicked)
        self.secondToolBar.addWidget(self.externalFileButton)

        editExternalFileButton = QPushButton()
        editExternalFileButton.setToolTip("Edit Topical Notes")
        editExternalFileButtonFile = os.path.join("htmlResources", "edit.png")
        editExternalFileButton.setIcon(QIcon(editExternalFileButtonFile))
        editExternalFileButton.clicked.connect(self.editExternalFileButtonClicked)
        self.secondToolBar.addWidget(editExternalFileButton)

        self.secondToolBar.addSeparator()

        fontMinusButton = QPushButton()
        fontMinusButton.setToolTip("Smaller Font Size")
        fontMinusButtonFile = os.path.join("htmlResources", "fontMinus.png")
        fontMinusButton.setIcon(QIcon(fontMinusButtonFile))
        fontMinusButton.clicked.connect(self.smallerFont)
        self.secondToolBar.addWidget(fontMinusButton)

        fontPlusButton = QPushButton()
        fontPlusButton.setToolTip("Larger Font Size")
        fontPlusButtonFile = os.path.join("htmlResources", "fontPlus.png")
        fontPlusButton.setIcon(QIcon(fontPlusButtonFile))
        fontPlusButton.clicked.connect(self.largerFont)
        self.secondToolBar.addWidget(fontPlusButton)

        self.secondToolBar.addSeparator()

        self.leftToolBar = QToolBar()
        self.leftToolBar.setWindowTitle("Left Toolbar")
        self.leftToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(Qt.LeftToolBarArea, self.leftToolBar)

        backButton = QPushButton()
        backButton.setToolTip("Main View Previous History Record")
        leftButtonFile = os.path.join("htmlResources", "left.png")
        backButton.setIcon(QIcon(leftButtonFile))
        backButton.clicked.connect(self.back)
        self.leftToolBar.addWidget(backButton)

        mainHistoryButton = QPushButton()
        mainHistoryButton.setToolTip("Main View History")
        mainHistoryButtonFile = os.path.join("htmlResources", "history.png")
        mainHistoryButton.setIcon(QIcon(mainHistoryButtonFile))
        mainHistoryButton.clicked.connect(self.mainHistoryButtonClicked)
        self.leftToolBar.addWidget(mainHistoryButton)

        forwardButton = QPushButton()
        forwardButton.setToolTip("Main View Next History Record")
        rightButtonFile = os.path.join("htmlResources", "right.png")
        forwardButton.setIcon(QIcon(rightButtonFile))
        forwardButton.clicked.connect(self.forward)
        self.leftToolBar.addWidget(forwardButton)

        self.leftToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Export to PDF")
        actionButtonFile = os.path.join("htmlResources", "pdf.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.printMainPage)
        self.leftToolBar.addWidget(actionButton)

        self.leftToolBar.addSeparator()

        self.enableParagraphButton = QPushButton()
        self.enableParagraphButton.setToolTip("Formatted / Plain Bibles \n(only if both versions are installed)")
        enableParagraphButtonFile = os.path.join("htmlResources", self.getReadFormattedBibles())
        self.enableParagraphButton.setIcon(QIcon(enableParagraphButtonFile))
        self.enableParagraphButton.clicked.connect(self.enableParagraphButtonClicked)
        self.leftToolBar.addWidget(self.enableParagraphButton)

        self.enableSubheadingButton = QPushButton()
        self.enableSubheadingButton.setToolTip("Add Sub-headings to Plain Bibles \n(only for plain versions)")
        enableSubheadingButtonFile = os.path.join("htmlResources", self.getAddSubheading())
        self.enableSubheadingButton.setIcon(QIcon(enableSubheadingButtonFile))
        self.enableSubheadingButton.clicked.connect(self.enableSubheadingButtonClicked)
        self.leftToolBar.addWidget(self.enableSubheadingButton)

        self.leftToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Preivous Chapter")
        actionButtonFile = os.path.join("htmlResources", "previousChapter.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.previousMainChapter)
        self.leftToolBar.addWidget(actionButton)

#        actionButton = QPushButton()
#        actionButton.setToolTip("Main Passage")
#        actionButtonFile = os.path.join("htmlResources", "bible.png")
#        actionButton.setIcon(QIcon(actionButtonFile))
#        actionButton.clicked.connect(self.openMainChapter)
#        self.leftToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Next Chapter")
        actionButtonFile = os.path.join("htmlResources", "nextChapter.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.nextMainChapter)
        self.leftToolBar.addWidget(actionButton)

        self.leftToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Compare All Versions")
        actionButtonFile = os.path.join("htmlResources", "compare_with.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runCOMPARE)
        self.leftToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Compare / Parallel with ...")
        actionButtonFile = os.path.join("htmlResources", "parallel_with.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.mainRefButtonClicked)
        self.leftToolBar.addWidget(actionButton)

        self.leftToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Marvel Original Bible")
        actionButtonFile = os.path.join("htmlResources", "original.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runMOB)
        self.leftToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Marvel Interlinear Bible")
        actionButtonFile = os.path.join("htmlResources", "interlinear.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runMIB)
        self.leftToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Marvel Trilingual Bible")
        actionButtonFile = os.path.join("htmlResources", "trilingual.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runMTB)
        self.leftToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Marvel Parallel Bible")
        actionButtonFile = os.path.join("htmlResources", "line.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runMPB)
        self.leftToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Marvel Annotated Bible")
        actionButtonFile = os.path.join("htmlResources", "annotated.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runMAB)
        self.leftToolBar.addWidget(actionButton)

        self.leftToolBar.addSeparator()

        self.rightToolBar = QToolBar()
        self.rightToolBar.setWindowTitle("Right Toolbar")
        self.rightToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(Qt.RightToolBarArea, self.rightToolBar)

        studyBackButton = QPushButton()
        studyBackButton.setToolTip("Study View Previous History Record")
        leftButtonFile = os.path.join("htmlResources", "left.png")
        studyBackButton.setIcon(QIcon(leftButtonFile))
        studyBackButton.clicked.connect(self.studyBack)
        self.rightToolBar.addWidget(studyBackButton)

        studyHistoryButton = QPushButton()
        studyHistoryButton.setToolTip("Study View History")
        studyHistoryButtonFile = os.path.join("htmlResources", "history.png")
        studyHistoryButton.setIcon(QIcon(studyHistoryButtonFile))
        studyHistoryButton.clicked.connect(self.studyHistoryButtonClicked)
        self.rightToolBar.addWidget(studyHistoryButton)

        studyForwardButton = QPushButton()
        studyForwardButton.setToolTip("Study View Next History Record")
        rightButtonFile = os.path.join("htmlResources", "right.png")
        studyForwardButton.setIcon(QIcon(rightButtonFile))
        studyForwardButton.clicked.connect(self.studyForward)
        self.rightToolBar.addWidget(studyForwardButton)

        self.rightToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Export to PDF")
        actionButtonFile = os.path.join("htmlResources", "pdf.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.printStudyPage)
        self.rightToolBar.addWidget(actionButton)

        self.rightToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Smart Indexes")
        actionButtonFile = os.path.join("htmlResources", "indexes.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runINDEX)
        self.rightToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Commentary")
        actionButtonFile = os.path.join("htmlResources", "commentary.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runCOMMENTARY)
        self.rightToolBar.addWidget(actionButton)

        self.rightToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Cross References")
        actionButtonFile = os.path.join("htmlResources", "cross_reference.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runCROSSREFERENCE)
        self.rightToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Treasury of Scripture Knowledge (Enhanced)")
        actionButtonFile = os.path.join("htmlResources", "treasure.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runTSKE)
        self.rightToolBar.addWidget(actionButton)

        self.rightToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Translations")
        actionButtonFile = os.path.join("htmlResources", "translations.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runTRANSLATION)
        self.rightToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Discourse Features")
        actionButtonFile = os.path.join("htmlResources", "discourse.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runDISCOURSE)
        self.rightToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Words")
        actionButtonFile = os.path.join("htmlResources", "words.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runWORDS)
        self.rightToolBar.addWidget(actionButton)

        actionButton = QPushButton()
        actionButton.setToolTip("Translations + Discourse Features + Words")
        actionButtonFile = os.path.join("htmlResources", "combo.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.runCOMBO)
        self.rightToolBar.addWidget(actionButton)

        self.rightToolBar.addSeparator()

        actionButton = QPushButton()
        actionButton.setToolTip("Landscape / Portrait Mode")
        actionButtonFile = os.path.join("htmlResources", "portrait.png")
        actionButton.setIcon(QIcon(actionButtonFile))
        actionButton.clicked.connect(self.switchLandscapeMode)
        self.rightToolBar.addWidget(actionButton)

        parallelButton = QPushButton()
        parallelButton.setToolTip("Resize / Hide Study View")
        parallelButtonFile = os.path.join("htmlResources", "parallel.png")
        parallelButton.setIcon(QIcon(parallelButtonFile))
        parallelButton.clicked.connect(self.parallel)
        self.rightToolBar.addWidget(parallelButton)

        self.rightToolBar.addSeparator()

        self.enableInstantButton = QPushButton()
        self.enableInstantButton.setToolTip("Enable / Disable Hovering Feature")
        enableInstantButtonFile = os.path.join("htmlResources", self.getInstantInformation())
        self.enableInstantButton.setIcon(QIcon(enableInstantButtonFile))
        self.enableInstantButton.clicked.connect(self.enableInstantButtonClicked)
        self.rightToolBar.addWidget(self.enableInstantButton)

        instantButton = QPushButton()
        instantButton.setToolTip("Show / Hide Bottom View")
        instantButtonFile = os.path.join("htmlResources", "lightning.png")
        instantButton.setIcon(QIcon(instantButtonFile))
        instantButton.clicked.connect(self.instant)
        self.rightToolBar.addWidget(instantButton)

        self.rightToolBar.addSeparator()

    def setupToolBarFullIconSize(self):

        textButtonStyle = "QPushButton {background-color: #151B54; color: white;} QPushButton:hover {background-color: #333972;} QPushButton:pressed { background-color: #515790;}"

        self.firstToolBar = QToolBar()
        self.firstToolBar.setWindowTitle("Main Toolbar")
        self.firstToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(self.firstToolBar)

        self.mainTextMenuButton = QPushButton(self.verseReference("main")[0])
        self.mainTextMenuButton.setToolTip("Main View Bible Menu")
        self.mainTextMenuButton.setStyleSheet(textButtonStyle)
        self.mainTextMenuButton.clicked.connect(self.mainTextMenu)
        self.firstToolBar.addWidget(self.mainTextMenuButton)

        self.mainRefButton = QPushButton(self.verseReference("main")[1])
        self.mainRefButton.setToolTip("Main View Active Verse Features")
        self.mainRefButton.setStyleSheet(textButtonStyle)
        self.mainRefButton.clicked.connect(self.mainRefButtonClicked)
        self.firstToolBar.addWidget(self.mainRefButton)

        iconFile = os.path.join("htmlResources", "noteChapter.png")
        self.firstToolBar.addAction(QIcon(iconFile), "Main View Chapter Notes", self.openMainChapterNote)

        iconFile = os.path.join("htmlResources", "noteVerse.png")
        self.firstToolBar.addAction(QIcon(iconFile), "Main View Verse Notes", self.openMainVerseNote)

        iconFile = os.path.join("htmlResources", "search.png")
        self.firstToolBar.addAction(QIcon(iconFile), "Search Last Opened Bible on Main View", self.displaySearchBibleCommand)

        iconFile = os.path.join("htmlResources", "search_plus.png")
        self.firstToolBar.addAction(QIcon(iconFile), "Search Last Opened Bible on Main View with {0}".format(config.iSearchVersion), self.displayISearchBibleCommand)

        self.firstToolBar.addSeparator()

        self.textCommandLineEdit = QLineEdit()
        self.textCommandLineEdit.setToolTip("Command Line")
        self.textCommandLineEdit.setMinimumWidth(100)
        self.textCommandLineEdit.returnPressed.connect(self.textCommandEntered)
        self.firstToolBar.addWidget(self.textCommandLineEdit)

        self.firstToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "toolbar.png")
        self.firstToolBar.addAction(QIcon(iconFile), "Show / Hide Other Toolbars", self.hideShowAdditionalToolBar)

        self.addToolBarBreak()

        self.studyBibleToolBar = QToolBar()
        self.studyBibleToolBar.setWindowTitle("Bible on Study View")
        self.studyBibleToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(self.studyBibleToolBar)

        self.studyTextMenuButton = QPushButton(self.verseReference("study")[0])
        self.studyTextMenuButton.setToolTip("Study View Bible Menu")
        self.studyTextMenuButton.setStyleSheet(textButtonStyle)
        self.studyTextMenuButton.clicked.connect(self.studyTextMenu)
        self.studyBibleToolBar.addWidget(self.studyTextMenuButton)

        self.studyRefButton = QPushButton(self.verseReference("study")[1])
        self.studyRefButton.setToolTip("Study View Active Verse Features")
        self.studyRefButton.setStyleSheet(textButtonStyle)
        self.studyRefButton.clicked.connect(self.studyRefButtonClicked)
        self.studyBibleToolBar.addWidget(self.studyRefButton)

        iconFile = os.path.join("htmlResources", "noteChapter.png")
        self.studyBibleToolBar.addAction(QIcon(iconFile), "Study View Chapter Notes", self.openStudyChapterNote)

        iconFile = os.path.join("htmlResources", "noteVerse.png")
        self.studyBibleToolBar.addAction(QIcon(iconFile), "Study View Verse Notes", self.openStudyVerseNote)

        iconFile = os.path.join("htmlResources", "search.png")
        self.studyBibleToolBar.addAction(QIcon(iconFile), "Search Last Opened Bible on Study View", self.displaySearchStudyBibleCommand)

        iconFile = os.path.join("htmlResources", "search_plus.png")
        self.studyBibleToolBar.addAction(QIcon(iconFile), "Search Last Opened Bible on Study View with {0}".format(config.iSearchVersion), self.displayISearchStudyBibleCommand)

        self.secondToolBar = QToolBar()
        self.secondToolBar.setWindowTitle("Secondary Toolbar")
        self.secondToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(self.secondToolBar)

        iconFile = os.path.join("htmlResources", self.getStudyBibleDisplay())
        self.enableStudyBibleButton = self.secondToolBar.addAction(QIcon(iconFile), self.getStudyBibleDisplayToolTip(), self.enableStudyBibleButtonClicked)

        self.secondToolBar.addSeparator()

        self.commentaryRefButton = QPushButton(self.verseReference("commentary"))
        self.commentaryRefButton.setToolTip("Commentary Menu")
        self.commentaryRefButton.setStyleSheet(textButtonStyle)
        self.commentaryRefButton.clicked.connect(self.commentaryRefButtonClicked)
        self.secondToolBar.addWidget(self.commentaryRefButton)

        self.secondToolBar.addSeparator()

        self.bookButton = QPushButton(config.book)
        self.bookButton.setToolTip("Books")
        self.bookButton.setStyleSheet(textButtonStyle)
        self.bookButton.clicked.connect(self.openBookMenu)
        self.secondToolBar.addWidget(self.bookButton)

#        searchBookButton = QPushButton()
#        searchBookButton.setToolTip("Search Books")
#        searchBookButtonFile = os.path.join("htmlResources", "search.png")
#        searchBookButton.setIcon(QIcon(searchBookButtonFile))
#        searchBookButton.clicked.connect(self.displaySearchBookCommand)
#        self.secondToolBar.addWidget(searchBookButton)

        self.secondToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "newfile.png")
        self.secondToolBar.addAction(QIcon(iconFile), "Create a Topical Note", self.createNewNoteFile)

        iconFile = os.path.join("htmlResources", "open.png")
        self.secondToolBar.addAction(QIcon(iconFile), "Open Topical Notes", self.openTextFileDialog)

        self.externalFileButton = QPushButton(self.getLastExternalFileName())
        self.externalFileButton.setToolTip("Read Topical Notes")
        self.externalFileButton.setStyleSheet(textButtonStyle)
        self.externalFileButton.clicked.connect(self.externalFileButtonClicked)
        self.secondToolBar.addWidget(self.externalFileButton)

        iconFile = os.path.join("htmlResources", "edit.png")
        self.secondToolBar.addAction(QIcon(iconFile), "Edit Topical Notes", self.editExternalFileButtonClicked)

        self.secondToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "fontMinus.png")
        self.secondToolBar.addAction(QIcon(iconFile), "Smaller Font Size", self.smallerFont)

        iconFile = os.path.join("htmlResources", "fontPlus.png")
        self.secondToolBar.addAction(QIcon(iconFile), "Larger Font Size", self.largerFont)

        self.secondToolBar.addSeparator()

        self.leftToolBar = QToolBar()
        self.leftToolBar.setWindowTitle("Left Toolbar")
        self.leftToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(Qt.LeftToolBarArea, self.leftToolBar)

        iconFile = os.path.join("htmlResources", "left.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Main View Previous History Record", self.back)

        iconFile = os.path.join("htmlResources", "history.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Main View History", self.mainHistoryButtonClicked)

        iconFile = os.path.join("htmlResources", "right.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Main View Next History Record", self.forward)

        self.leftToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "pdf.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Export to PDF", self.printMainPage)

        self.leftToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", self.getReadFormattedBibles())
        self.enableParagraphButton = self.leftToolBar.addAction(QIcon(iconFile), "Formatted / Plain Bibles \n(only if both versions are installed)", self.enableParagraphButtonClicked)

        iconFile = os.path.join("htmlResources", self.getAddSubheading())
        self.enableSubheadingButton = self.leftToolBar.addAction(QIcon(iconFile), "Add Sub-headings to Plain Bibles \n(only for plain versions)", self.enableSubheadingButtonClicked)

        self.leftToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "previousChapter.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Preivous Chapter", self.previousMainChapter)

#        actionButton = QPushButton()
#        actionButton.setToolTip("Main Passage")
#        actionButtonFile = os.path.join("htmlResources", "bible.png")
#        actionButton.setIcon(QIcon(actionButtonFile))
#        actionButton.clicked.connect(self.openMainChapter)
#        self.leftToolBar.addWidget(actionButton)

        iconFile = os.path.join("htmlResources", "nextChapter.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Next Chapter", self.nextMainChapter)

        self.leftToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "compare_with.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Compare All Versions", self.runCOMPARE)

        iconFile = os.path.join("htmlResources", "parallel_with.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Compare / Parallel with ...", self.mainRefButtonClicked)

        self.leftToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "original.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Marvel Original Bible", self.runMOB)

        iconFile = os.path.join("htmlResources", "interlinear.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Marvel Interlinear Bible", self.runMIB)

        iconFile = os.path.join("htmlResources", "trilingual.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Marvel Trilingual Bible", self.runMTB)

        iconFile = os.path.join("htmlResources", "line.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Marvel Parallel Bible", self.runMPB)

        iconFile = os.path.join("htmlResources", "annotated.png")
        self.leftToolBar.addAction(QIcon(iconFile), "Marvel Annotated Bible", self.runMAB)

        self.leftToolBar.addSeparator()

        self.rightToolBar = QToolBar()
        self.rightToolBar.setWindowTitle("Right Toolbar")
        self.rightToolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(Qt.RightToolBarArea, self.rightToolBar)

        iconFile = os.path.join("htmlResources", "left.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Study View Previous History Record", self.studyBack)

        iconFile = os.path.join("htmlResources", "history.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Study View History", self.studyHistoryButtonClicked)

        iconFile = os.path.join("htmlResources", "right.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Study View Next History Record", self.studyForward)

        self.rightToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "pdf.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Export to PDF", self.printStudyPage)

        self.rightToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "indexes.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Smart Indexes", self.runINDEX)

        iconFile = os.path.join("htmlResources", "commentary.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Commentary", self.runCOMMENTARY)

        self.rightToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "cross_reference.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Cross References", self.runCROSSREFERENCE)

        iconFile = os.path.join("htmlResources", "treasure.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Treasury of Scripture Knowledge (Enhanced)", self.runTSKE)

        self.rightToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "translations.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Translations", self.runTRANSLATION)

        iconFile = os.path.join("htmlResources", "discourse.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Discourse Features", self.runDISCOURSE)

        iconFile = os.path.join("htmlResources", "words.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Words", self.runWORDS)

        iconFile = os.path.join("htmlResources", "combo.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Translations + Discourse Features + Words", self.runCOMBO)

        self.rightToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "portrait.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Landscape / Portrait Mode", self.switchLandscapeMode)

        iconFile = os.path.join("htmlResources", "parallel.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Resize / Hide Study View", self.parallel)

        self.rightToolBar.addSeparator()

        iconFile = os.path.join("htmlResources", self.getInstantInformation())
        self.enableInstantButton = self.rightToolBar.addAction(QIcon(iconFile), "Enable / Disable Hovering Feature", self.enableInstantButtonClicked)

        iconFile = os.path.join("htmlResources", "lightning.png")
        self.rightToolBar.addAction(QIcon(iconFile), "Show / Hide Bottom View", self.instant)

        self.rightToolBar.addSeparator()

    def setStudyBibleToolBar(self):
        if config.openBibleInMainViewOnly:
            self.studyBibleToolBar.hide()
        else:
            self.studyBibleToolBar.show()

    # install marvel data
    def installMarvelBibles(self):
        bibles = {
            "American Standard Version": (("marvelData", "bibles", "ASV.bible"), "1oDuV54_zOl_L0GQqmYiLvgjk2pQu4iSr"),
            "Berean Study Bible": (("marvelData", "bibles", "BSB.bible"), "1fQX8cT12LE9Q3dBUJyezTYg4a0AbdKbN"),
            "Chinese Union Version (Traditional Chinese)": (("marvelData", "bibles", "CUV.bible"), "1iqsHxOWD_H-BABbjq03qIIrTu8u-UyjJ"),
            "Chinese Union Version (Simplified Chinese)": (("marvelData", "bibles", "CUVs.bible"), "1neY4KK3tfVtmnoLQu6YVMCyIhqcFEiPZ"),
            "International Standard Version": (("marvelData", "bibles", "ISV.bible"), "1_nmaakABx8wVsQHdBL9rVh2wtRK8uyyW"),
            "King James Version": (("marvelData", "bibles", "KJV.bible"), "1ycOkEJ2JI_4iwjllb4mE02wkDvrsPlNq"),
            "Lexhame English Bible": (("marvelData", "bibles", "LEB.bible"), "1p-_phmh3y54i4FSLhzEd33_v0kzSjAZn"),
            "Septuagint / LXX [main]": (("marvelData", "bibles", "LXX1.bible"), "1sjPa7oP9SnsrsPyQ1JPUGbwgMT8QE8F1"),
            "Septuagint / LXX interlinear [main]": (("marvelData", "bibles", "LXX1i.bible"), "1pxj_pg7412ZA9ojnkI1iV46c6J3_7SJ9"),
            "Septuagint / LXX [alternate]": (("marvelData", "bibles", "LXX2.bible"), "1fK99KgtdFhEQssvYVp3fPQZNJBFBpEca"),
            "Septuagint / LXX interlinear [alternate]": (("marvelData", "bibles", "LXX2i.bible"), "1E-i68TbbxxvDTzzzl-aFTXwmsro9LUjZ"),
            "Marvel Annotated Bible": (("marvelData", "bibles", "MAB.bible"), "1baA_5OkjO6-dk2dIQ4rcJ2VaAZqy1gRT"),
            "Marvel Interlinear Bible": (("marvelData", "bibles", "MIB.bible"), "106g4L5fO5UBjzGv641H0rdXFvTB9COvs"),
            "Marvel Original Bible": (("marvelData", "bibles", "MOB.bible"), "1OG28pqdbEOxk1Kjly6EPvsMDRXJ4_RsR"),
            "Marvel Parallel Bible": (("marvelData", "bibles", "MPB.bible"), "1gl2KDzxXIjXOC71ZYVQZduAzqaSK3fEU"),
            "Marvel Trilingual Bible": (("marvelData", "bibles", "MTB.bible"), "1HqJoGzWrsPqkys3IydAbogZ5NeI47WE8"),
            "New English Translation": (("marvelData", "bibles", "NET.bible"), "1pJ_9Wk4CmDdFO08wioOxs4krKjNeh4Ur"),
            "unfoldingWord Literal Text": (("marvelData", "bibles", "ULT.bible"), "10Udo5ND0a26hPIcJHNOuNqJ2feZuVXjT"),
            "unfoldingWord Simplified Text": (("marvelData", "bibles", "UST.bible"), "1OFwdXRwC9gG4PJLt5j4NHWgFs9wcgXQk"),
            "World English Bible": (("marvelData", "bibles", "WEB.bible"), "1L9qAeamdZwGzVdf7jC4_ks05hyQa2R7l"),
        }
        items = [bible for bible in bibles.keys() if not os.path.isfile(os.path.join(*bibles[bible][0]))]
        if not items:
            items = ["[All Installed]"]
        item, ok = QInputDialog.getItem(self, "Install Formatted Bibles",
                "Available Modules:", items, 0, False)
        if ok and item and not item == "[All Installed]":
            self.downloadHelper(bibles[item])

    def installMarvelCommentaries(self):
        commentaries = {
            "Notes on the Old and New Testaments (Barnes) [26 vol.]": (("marvelData", "commentaries", "cBarnes.commentary"), "13uxButnFH2NRUV-YuyRZYCeh1GzWqO5J"),
            "Commentary on the Old and New Testaments (Benson) [5 vol.]": (("marvelData", "commentaries", "cBenson.commentary"), "1MSRUHGDilogk7_iZHVH5GWkPyf8edgjr"),
            "Biblical Illustrator (Exell) [58 vol.]": (("marvelData", "commentaries", "cBI.commentary"), "1DUATP_0M7SwBqsjf20YvUDblg3_sOt2F"),
            "Complete Summary of the Bible (Brooks) [2 vol.]": (("marvelData", "commentaries", "cBrooks.commentary"), "1pZNRYE6LqnmfjUem4Wb_U9mZ7doREYUm"),
            "John Calvin's Commentaries (Calvin) [22 vol.]": (("marvelData", "commentaries", "cCalvin.commentary"), "1FUZGK9n54aXvqMAi3-2OZDtRSz9iZh-j"),
            "Cambridge Bible for Schools and Colleges (Cambridge) [57 vol.]": (("marvelData", "commentaries", "cCBSC.commentary"), "1IxbscuAMZg6gQIjzMlVkLtJNDQ7IzTh6"),
            "Critical And Exegetical Commentary on the NT (Meyer) [20 vol.]": (("marvelData", "commentaries", "cCECNT.commentary"), "1MpBx7z6xyJYISpW_7Dq-Uwv0rP8_Mi-r"),
            "Cambridge Greek Testament for Schools and Colleges (Cambridge) [21 vol.]": (("marvelData", "commentaries", "cCGrk.commentary"), "1Jf51O0R911Il0V_SlacLQDNPaRjumsbD"),
            "Church Pulpit Commentary (Nisbet) [12 vol.]": (("marvelData", "commentaries", "cCHP.commentary"), "1dygf2mz6KN_ryDziNJEu47-OhH8jK_ff"),
            "Commentary on the Bible (Clarke) [6 vol.]": (("marvelData", "commentaries", "cClarke.commentary"), "1ZVpLAnlSmBaT10e5O7pljfziLUpyU4Dq"),
            "College Press Bible Study Textbook Series (College) [59 vol.]": (("marvelData", "commentaries", "cCPBST.commentary"), "14zueTf0ioI-AKRo_8GK8PDRKael_kB1U"),
            "Expositor's Bible Commentary (Nicoll) [49 vol.]": (("marvelData", "commentaries", "cEBC.commentary"), "1UA3tdZtIKQEx-xmXtM_SO1k8S8DKYm6r"),
            "Commentary for English Readers (Ellicott) [8 vol.]": (("marvelData", "commentaries", "cECER.commentary"), "1sCJc5xuxqDDlmgSn2SFWTRbXnHSKXeh_"),
            "Expositor's Greek New Testament (Nicoll) [5 vol.]": (("marvelData", "commentaries", "cEGNT.commentary"), "1ZvbWnuy2wwllt-s56FUfB2bS2_rZoiPx"),
            "Greek Testament Commentary (Alford) [4 vol.]": (("marvelData", "commentaries", "cGCT.commentary"), "1vK53UO2rggdcfcDjH6mWXAdYti4UbzUt"),
            "Exposition of the Entire Bible (Gill) [9 vol.]": (("marvelData", "commentaries", "cGill.commentary"), "1O5jnHLsmoobkCypy9zJC-Sw_Ob-3pQ2t"),
            "Exposition of the Old and New Testaments (Henry) [6 vol.]": (("marvelData", "commentaries", "cHenry.commentary"), "1m-8cM8uZPN-fLVcC-a9mhL3VXoYJ5Ku9"),
            "Horæ Homileticæ (Simeon) [21 vol.]": (("marvelData", "commentaries", "cHH.commentary"), "1RwKN1igd1RbN7phiJDiLPhqLXdgOR0Ms"),
            "International Critical Commentary, NT (1896-1929) [16 vol.]": (("marvelData", "commentaries", "cICCNT.commentary"), "1QxrzeeZYc0-GNwqwdDe91H4j1hGSOG6t"),
            "Jamieson, Fausset, and Brown Commentary (JFB) [6 vol.]": (("marvelData", "commentaries", "cJFB.commentary"), "1NT02QxoLeY3Cj0uA_5142P5s64RkRlpO"),
            "Commentary on the Old Testament (Keil & Delitzsch) [10 vol.]": (("marvelData", "commentaries", "cKD.commentary"), "1rFFDrdDMjImEwXkHkbh7-vX3g4kKUuGV"),
            "Commentary on the Holy Scriptures: Critical, Doctrinal, and Homiletical (Lange) [25 vol.]": (("marvelData", "commentaries", "cLange.commentary"), "1_PrTT71aQN5LJhbwabx-kjrA0vg-nvYY"),
            "Expositions of Holy Scripture (MacLaren) [32 vol.]": (("marvelData", "commentaries", "cMacL.commentary"), "1p32F9MmQ2wigtUMdCU-biSrRZWrFLWJR"),
            "Preacher's Complete Homiletical Commentary (Exell) [37 vol.]": (("marvelData", "commentaries", "cPHC.commentary"), "1xTkY_YFyasN7Ks9me3uED1HpQnuYI8BW"),
            "Pulpit Commentary (Spence) [23 vol.]": (("marvelData", "commentaries", "cPulpit.commentary"), "1briSh0oDhUX7QnW1g9oM3c4VWiThkWBG"),
            "Word Pictures in the New Testament (Robertson) [6 vol.]": (("marvelData", "commentaries", "cRob.commentary"), "17VfPe4wsnEzSbxL5Madcyi_ubu3iYVkx"),
            "Spurgeon's Expositions on the Bible (Spurgeon) [3 vol.]": (("marvelData", "commentaries", "cSpur.commentary"), "1OVsqgHVAc_9wJBCcz6PjsNK5v9GfeNwp"),
            "Word Studies in the New Testament (Vincent) [4 vol.]": (("marvelData", "commentaries", "cVincent.commentary"), "1ZZNnCo5cSfUzjdEaEvZ8TcbYa4OKUsox"),
            "John Wesley's Notes on the Whole Bible (Wesley) [3 vol.]": (("marvelData", "commentaries", "cWesley.commentary"), "1rerXER1ZDn4e1uuavgFDaPDYus1V-tS5"),
            "Commentary on the Old and New Testaments (Whedon) [14 vol.]": (("marvelData", "commentaries", "cWhedon.commentary"), "1FPJUJOKodFKG8wsNAvcLLc75QbM5WO-9"),
        }
        items = [commentary for commentary in commentaries.keys() if not os.path.isfile(os.path.join(*commentaries[commentary][0]))]
        if items:
            commentaries["Install ALL Commentaries Listed Above"] = ""
            items.append("Install ALL Commentaries Listed Above")
        else:
            items = ["[All Installed]"]
        item, ok = QInputDialog.getItem(self, "Install Bible Commentaries",
                "Available Modules:", items, 0, False)
        if ok and item and not item in ("[All Installed]", "Install ALL Commentaries Listed Above"):
            self.downloadHelper(commentaries[item])
        elif item == "Install ALL Commentaries Listed Above":
            self.installAllMarvelCommentaries(commentaries)

    def installAllMarvelCommentaries(self, commentaries):
        toBeInstalled = [commentary for commentary in commentaries.keys() if not commentary == "Install ALL Commentaries Listed Above" and not os.path.isfile(os.path.join(*commentaries[commentary][0]))]
        self.mainPage.runJavaScript('alert("It takes time to install all Marvel.bible commentaries. You will receive another message when files are downloaded.")')
        for commentary in toBeInstalled:
            databaseInfo = commentaries[commentary]
            downloader = Downloader(self, databaseInfo)
            downloader.downloadFile(False)
        self.mainPage.runJavaScript('alert("All Marvel.bible commentaries installed.")')

    def installMarvelDatasets(self):
        datasets = {
            "Core Datasets": (("marvelData", "morphology.sqlite"), "1Vn3UXicjqDQSA41ek3_zJ7n2iAlspU_3"),
            "Search Engine": (("marvelData", "search.sqlite"), "1A4s8ewpxayrVXamiva2l1y1AinAcIKAh"),
            "Smart Indexes": (("marvelData", "indexes.sqlite"), "1Fdq3C9hyoyBX7riniByyZdW9mMoMe6EX"),
            "Chapter & Verse Notes": (("marvelData", "note.sqlite"), "1OcHrAXLS-OLDG5Q7br6mt2WYCedk8lnW"),
            "Bible Background Data": (("marvelData", "data", "exlb.data"), "1kA5appVfyQ1lWF1czEQWtts4idogHIpa"),
            "Bible Topics Data": (("marvelData", "data", "exlb.data"), "1kA5appVfyQ1lWF1czEQWtts4idogHIpa"),
            "Cross-reference Data": (("marvelData", "cross-reference.sqlite"), "1gZNqhwER_-IWYPaMNGZ229teJ5cSA7My"),
            "Dictionaries": (("marvelData", "data", "dictionary.data"), "1NfbkhaR-dtmT1_Aue34KypR3mfPtqCZn"),
            "Encyclopedia": (("marvelData", "data", "encyclopedia.data"), "1OuM6WxKfInDBULkzZDZFryUkU1BFtym8"),
            "Lexicons": (("marvelData", "lexicons", "MCGED.lexicon"), "157Le0xw2ovuoF2v9Bf6qeck0o15RGfMM"),
            "Atlas, Timelines & Books": (("marvelData", "books", "Timelines.book"), "1nuhrsujL6LYYeviaT22Rhn_wk9kc6una"),
            "Word Data": (("marvelData", "data", "wordNT.data"), "11pmVhecYEtklcB4fLjNP52eL9pkytFdS"),
            "Words Data": (("marvelData", "data", "wordsNT.data"), "11bANQQhH6acVujDXiPI4JuaenTFYTkZA"),
            "Clause Data": (("marvelData", "data", "clauseNT.data"), "11pmVhecYEtklcB4fLjNP52eL9pkytFdS"),
            "Translation Data": (("marvelData", "data", "translationNT.data"), "11bANQQhH6acVujDXiPI4JuaenTFYTkZA"),
            "Discourse Data": (("marvelData", "data", "discourseNT.data"), "11bANQQhH6acVujDXiPI4JuaenTFYTkZA"),
            "TDW Combo Data": (("marvelData", "data", "wordsNT.data"), "11bANQQhH6acVujDXiPI4JuaenTFYTkZA"),
        }
        items = [dataset for dataset in datasets.keys() if not os.path.isfile(os.path.join(*datasets[dataset][0]))]
        if not items:
            items = ["[All Installed]"]
        item, ok = QInputDialog.getItem(self, "Install Marvel.bible Datasets",
                "Available Modules:", items, 0, False)
        if ok and item and not item == "[All Installed]":
            self.downloadHelper(datasets[item])

    # convert bible references to string
    def bcvToVerseReference(self, b, c, v):
        parser = BibleVerseParser(config.parserStandarisation)
        verseReference = parser.bcvToVerseReference(b, c, v)
        del parser
        return verseReference

    # Open text on left and right view
    def openTextOnMainView(self, text):
        if sys.getsizeof(text) < 2097152:
            self.mainView.setHtml(text, baseUrl)
        else:
            # write text in a text file
            # reason: setHTML does not work with content larger than 2 MB
            outputFile = os.path.join("htmlResources", "main.html")
            fileObject = open(outputFile, 'w')
            fileObject.write(text)
            fileObject.close()
            # open the text file with webview
            fullOutputPath = os.path.abspath(outputFile)
            self.mainView.load(QUrl.fromLocalFile(fullOutputPath))
        reference = " - ".join(self.verseReference("main"))
        if self.textCommandParser.lastKeyword in ("compare", "parallel"):
            *_, reference2 = reference.split(" - ")
            reference = "{0} - {1}".format(self.textCommandParser.lastKeyword, reference2)
        self.mainView.setTabText(self.mainView.currentIndex(), reference)
        self.mainView.setTabToolTip(self.mainView.currentIndex(), reference)

    def openTextOnStudyView(self, text):
#        testing
#        currentIndex = self.studyView.currentIndex()
#        if currentIndex == 4:
#            nextIndex = 0
#        else:
#            nextIndex = currentIndex + 1
#        self.studyView.setCurrentWidget(self.studyView.widget(nextIndex))
        if sys.getsizeof(text) < 2097152:
            self.studyView.setHtml(text, baseUrl)
        else:
            # write text in a text file
            # reason: setHTML does not work with content larger than 2 MB
            outputFile = os.path.join("htmlResources", "study.html")
            fileObject = open(outputFile, 'w')
            fileObject.write(text)
            fileObject.close()
            # open the text file with webview
            fullOutputPath = os.path.abspath(outputFile)
            self.studyView.load(QUrl.fromLocalFile(fullOutputPath))
        if config.parallelMode == 0:
            self.parallel()
        self.studyView.setTabText(self.studyView.currentIndex(), self.textCommandParser.lastKeyword)
        self.studyView.setTabToolTip(self.studyView.currentIndex(), self.textCommandParser.lastKeyword)

    # warning for next action without saving modified notes
    def warningNotSaved(self):
        msgBox = QMessageBox(QMessageBox.Warning,
                "QMessageBox.warning()", "Notes are currently opened and modified.  Do you really want to continue, without saving the changes?",
                QMessageBox.NoButton, self)
        msgBox.addButton("Cancel", QMessageBox.AcceptRole)
        msgBox.addButton("&Continue", QMessageBox.RejectRole)
        if msgBox.exec_() == QMessageBox.AcceptRole:
            # Cancel
            return False
        else:
            # Continue
            return True

    # Actions - chapter / verse / new file note
    def createNewNoteFile(self):
        if self.noteSaved:
            self.noteEditor = NoteEditor(self, "file")
            self.noteEditor.show()
        elif self.warningNotSaved():
            self.noteEditor = NoteEditor(self, "file")
            self.noteEditor.show()
        else:
            self.noteEditor.raise_()

    def openNoteEditor(self, noteType):
        self.noteEditor = NoteEditor(self, noteType)
        self.noteEditor.show()

    def openMainChapterNote(self):
        self.openChapterNote(config.mainB, config.mainC)

    def openMainVerseNote(self):
        self.openVerseNote(config.mainB, config.mainC, config.mainV)

    def openStudyChapterNote(self):
        self.openChapterNote(config.studyB, config.studyC)

    def openStudyVerseNote(self):
        self.openVerseNote(config.studyB, config.studyC, config.studyV)

    def openChapterNote(self, b, c):
        self.textCommandParser.lastKeyword = "note"
        reference = BibleVerseParser(config.parserStandarisation).bcvToVerseReference(b, c, 1)
        config.studyB, config.studyC, config.studyV = b, c, 1
        self.updateStudyRefButton()
        config.commentaryB, config.commentaryC, config.commentaryV = b, c, 1
        self.updateCommentaryRefButton()
        noteSqlite = NoteSqlite()
        note = "<p><b>Note on {0}</b> &ensp;<button class='feature' onclick='document.title=\"_editchapternote:::\"'>edit</button></p>{1}".format(reference[:-2], noteSqlite.displayChapterNote((b, c)))
        del noteSqlite
        note = self.htmlWrapper(note, True, "study", False)
        self.openTextOnStudyView(note)

    def openVerseNote(self, b, c, v):
        self.textCommandParser.lastKeyword = "note"
        reference = BibleVerseParser(config.parserStandarisation).bcvToVerseReference(b, c, v)
        config.studyB, config.studyC, config.studyV = b, c, v
        self.updateStudyRefButton()
        config.commentaryB, config.commentaryC, config.commentaryV = b, c, v
        self.updateCommentaryRefButton()
        noteSqlite = NoteSqlite()
        note = "<p><b>Note on {0}</b> &ensp;<button class='feature' onclick='document.title=\"_editversenote:::\"'>edit</button></p>{1}".format(reference, noteSqlite.displayVerseNote((b, c, v)))
        del noteSqlite
        note = self.htmlWrapper(note, True, "study", False)
        self.openTextOnStudyView(note)

    # Actions - open text from external sources
    def htmlWrapper(self, text, parsing=False, view="study", linebreak=True):
        searchReplace1 = (
            ("\r\n|\r|\n", "<br>"),
            ("\t", "&emsp;&emsp;"),
        )
        searchReplace2 = (
            ("<br>(<table>|<ol>|<ul>)", r"\1"),
            ("(</table>|</ol>|</ul>)<br>", r"\1"),
            ("<a [^\n<>]*?href=['{0}]([^\n<>]*?)['{0}][^\n<>]*?>".format('"'), r"<a href='javascript:void(0)' onclick='website({0}\1{0})'>".format('"')),
            ("onclick='website\({0}([^\n<>]*?).uba{0}\)'".format('"'), r"onclick='uba({0}\1.uba{0})'".format('"'))
        )
        if linebreak:
            for search, replace in searchReplace1:
                text = re.sub(search, replace, text)
        for search, replace in searchReplace2:
            text = re.sub(search, replace, text)
        if parsing:
            text = BibleVerseParser(config.parserStandarisation).parseText(text)
        if view == "main":
            activeBCVsettings = "<script>var activeText = '{0}'; var activeB = {1}; var activeC = {2}; var activeV = {3};</script>".format(config.mainText, config.mainB, config.mainC, config.mainV)
        elif view == "study":
            activeBCVsettings = "<script>var activeText = '{0}'; var activeB = {1}; var activeC = {2}; var activeV = {3};</script>".format(config.studyText, config.studyB, config.studyC, config.studyV)
        text = "<!DOCTYPE html><html><head><title>UniqueBible.app</title><link rel='stylesheet' type='text/css' href='theText.css'><script src='theText.js'></script><script src='w3.js'></script>{0}<script>var versionList = []; var compareList = []; var parallelList = [];</script></head><body style='font-size: {1}%;'><span id='v0.0.0'></span>{2}</body></html>".format(activeBCVsettings, config.fontSize, text)
        return text

    def pasteFromClipboard(self):
        clipboardText = qApp.clipboard().text()
        # note: use qApp.clipboard().setText to set text in clipboard
        self.openTextOnStudyView(self.htmlWrapper(clipboardText, True))

    def openTextFileDialog(self):
        options = QFileDialog.Options()
        fileName, filtr = QFileDialog.getOpenFileName(self,
                "QFileDialog.getOpenFileName()",
                self.openFileNameLabel.text(),
                "UniqueBible.app Note Files (*.uba);;HTML Files (*.html);;HTM Files (*.htm);;Word Documents (*.docx);;Plain Text Files (*.txt);;PDF Files (*.pdf);;All Files (*)", "", options)
        if fileName:
            self.openTextFile(fileName)

    def openTextFile(self, fileName):
        self.textCommandParser.lastKeyword = "file"
        functions = {
            "pdf": self.openPdfFile,
            "docx": self.openDocxFile,
            "uba": self.openUbaFile,
            "html": self.openUbaFile,
            "htm": self.openUbaFile,
        }
        function = functions.get(fileName.split(".")[-1].lower(), self.openTxtFile)
        function(fileName)
        self.addExternalFileHistory(fileName)
        self.setExternalFileButton()

    def addExternalFileHistory(self, fileName):
        externalFileHistory = config.history['external']
        if externalFileHistory == [] or externalFileHistory[-1] != fileName:
            if fileName in externalFileHistory:
                externalFileHistory.remove(fileName)
            externalFileHistory.append(fileName)

    def setExternalFileButton(self):
        self.externalFileButton.setText(self.getLastExternalFileName())

    def getLastExternalFileName(self):
        externalFileHistory = config.history["external"]
        if externalFileHistory:
            return os.path.split(externalFileHistory[-1])[-1]
        else:
            return "[open file]"

    def externalFileButtonClicked(self):
        externalFileHistory = config.history["external"]
        if externalFileHistory:
            self.openExternalFileHistoryRecord(-1)
        else:
            self.openTextFileDialog()

    def editExternalFileButtonClicked(self):
        externalFileHistory = config.history["external"]
        if externalFileHistory:
            self.editExternalFileHistoryRecord(-1)
        else:
            self.openTextFileDialog()

    def editExternalFileHistoryRecord(self, record):
        file = config.history["external"][record]
        fileExtension = file.split(".")[-1].lower()
        directEdit = ("uba", "html", "htm")
        if fileExtension in directEdit:
            if self.noteSaved:
                self.noteEditor = NoteEditor(self, "file", file)
                self.noteEditor.show()
            elif self.warningNotSaved():
                self.noteEditor = NoteEditor(self, "file", file)
                self.noteEditor.show()
            else:
                self.noteEditor.raise_()
        else:
            self.openExternalFile(file)

    def openExternalFile(self, file):
        if platform.system() == "Linux":
            subprocess.call(["xdg-open", file])
        elif platform.system() == "Darwin":
            os.system("open {0}".format(file))
        elif platform.system() == "Windows":
            os.system("start {0}".format(file))

    def openExternalFileHistoryRecord(self, record):
        self.openTextFile(config.history["external"][record])

    def openExternalFileHistory(self):
        self.studyView.setHtml(self.getHistory("external"), baseUrl)

    def openTxtFile(self, fileName):
        if fileName:
            text = TextFileReader().readTxtFile(fileName)
            text = self.htmlWrapper(text, True)
            self.openTextOnStudyView(text)

    def openUbaFile(self, fileName):
        if fileName:
            text = TextFileReader().readTxtFile(fileName)
            text = self.htmlWrapper(text, True, "study", False)
            self.openTextOnStudyView(text)

    def openPdfFile(self, fileName):
        if fileName:
            text = TextFileReader().readPdfFile(fileName)
            text = self.htmlWrapper(text, True)
            self.openTextOnStudyView(text)

    def openDocxFile(self, fileName):
        if fileName:
            text = TextFileReader().readDocxFile(fileName)
            text = self.htmlWrapper(text, True)
            self.openTextOnStudyView(text)

    # Actions - export to pdf
    def printMainPage(self):
        file = "UniqueBible.app.pdf"
        self.mainPage.printToPdf(file)

    def printStudyPage(self):
        file = "UniqueBible.app.pdf"
        self.studyPage.printToPdf(file)

    # import BibleBentoPlus modules
    def importBBPlusLexiconInAFolder(self):
        options = QFileDialog.DontResolveSymlinks | QFileDialog.ShowDirsOnly
        directory = QFileDialog.getExistingDirectory(self,
                "QFileDialog.getExistingDirectory()",
                self.directoryLabel.text(), options)
        if directory:
            if Converter().importBBPlusLexiconInAFolder(directory):
                self.mainPage.runJavaScript("alert('Multiple BibleBento Plus lexicons imported.')")
            else:
                self.mainPage.runJavaScript("alert('No supported module is found in the selected folder.')")

    def importBBPlusDictionaryInAFolder(self):
        options = QFileDialog.DontResolveSymlinks | QFileDialog.ShowDirsOnly
        directory = QFileDialog.getExistingDirectory(self,
                "QFileDialog.getExistingDirectory()",
                self.directoryLabel.text(), options)
        if directory:
            if Converter().importBBPlusDictionaryInAFolder(directory):
                self.mainPage.runJavaScript("alert('Multiple BibleBento Plus dictionaries imported.')")
            else:
                self.mainPage.runJavaScript("alert('No supported module is found in the selected folder.')")

    # import 3rd party modules
    def importSettingsDialog(self):
        self.importSettings = ImportSettings(self)
        self.importSettings.show()

    def importModules(self):
        options = QFileDialog.Options()
        fileName, filtr = QFileDialog.getOpenFileName(self,
                "QFileDialog.getOpenFileName()",
                self.openFileNameLabel.text(),
                "MySword Bibles (*.bbl.mybible);;MySword Commentaries (*.cmt.mybible);;MySword Dictionaries (*.dct.mybible);;e-Sword Bibles [Apple] (*.bbli);;e-Sword Commentaries [Apple] (*.cmti);;e-Sword Dictionaries [Apple] (*.dcti);;e-Sword Lexicons [Apple] (*.lexi);;e-Sword Books [Apple] (*.refi);;MyBible Bibles (*.SQLite3);;MyBible Commentaries (*.commentaries.SQLite3);;MyBible Dictionaries (*.dictionary.SQLite3)", "", options)
        if fileName:
            if fileName.endswith(".dct.mybible") or fileName.endswith(".dcti") or fileName.endswith(".lexi") or fileName.endswith(".dictionary.SQLite3"):
                self.importThirdPartyDictionary(fileName)
            elif fileName.endswith(".bbl.mybible"):
                self.importMySwordBible(fileName)
            elif fileName.endswith(".cmt.mybible"):
                self.importMySwordCommentary(fileName)
            elif fileName.endswith(".bbli"):
                self.importESwordBible(fileName)
            elif fileName.endswith(".cmti"):
                self.importESwordCommentary(fileName)
            elif fileName.endswith(".refi"):
                self.importESwordBook(fileName)
            elif fileName.endswith(".commentaries.SQLite3"):
                self.importMyBibleCommentary(fileName)
            elif fileName.endswith(".SQLite3"):
                self.importMyBibleBible(fileName)

    def importModulesInFolder(self):
        options = QFileDialog.DontResolveSymlinks | QFileDialog.ShowDirsOnly
        directory = QFileDialog.getExistingDirectory(self,
                "QFileDialog.getExistingDirectory()",
                self.directoryLabel.text(), options)
        if directory:
            if Converter().importAllFilesInAFolder(directory):
                self.mainPage.runJavaScript("alert('Multiple 3rd party modules imported.')")
            else:
                self.mainPage.runJavaScript("alert('No supported module is found in the selected folder.')")

    def importThirdPartyDictionary(self, fileName):
        *_, name = os.path.split(fileName)
        destination = os.path.join("thirdParty", "dictionaries", name)
        try:
            copyfile(fileName, destination)
            self.completeImport()
        except:
            print("Failed to copy '{0}'.".format(fileName))

    def importMySwordBible(self, fileName):
        Converter().importMySwordBible(fileName)
        self.completeImport()

    def importMySwordCommentary(self, fileName):
        Converter().importMySwordCommentary(fileName)
        self.completeImport()

    def importESwordBible(self, fileName):
        Converter().importESwordBible(fileName)
        self.completeImport()

    def importESwordCommentary(self, fileName):
        Converter().importESwordCommentary(fileName)
        self.completeImport()

    def importESwordBook(self, fileName):
        Converter().importESwordBook(fileName)
        self.completeImport()

    def importMyBibleCommentary(self, fileName):
        Converter().importMyBibleCommentary(fileName)
        self.completeImport()

    def importMyBibleBible(self, fileName):
        Converter().importMyBibleBible(fileName)
        self.completeImport()

    def completeImport(self):
        self.mainPage.runJavaScript("alert('3rd Party Module Installed.')")

    # Actions - tag files with BibleVerseParser
    def onTaggingCompleted(self):
        self.mainPage.runJavaScript("alert('Finished. Tagged file(s) is/are named with a prefix \"tagged_\".')")

    def tagFile(self):
        options = QFileDialog.Options()
        fileName, filtr = QFileDialog.getOpenFileName(self,
                "QFileDialog.getOpenFileName()",
                self.openFileNameLabel.text(),
                "All Files (*);;Text Files (*.txt);;CSV Files (*.csv);;TSV Files (*.tsv)", "", options)
        if fileName:
            BibleVerseParser(config.parserStandarisation).startParsing(fileName)
            self.onTaggingCompleted()

    def tagFiles(self):
        options = QFileDialog.Options()
        files, filtr = QFileDialog.getOpenFileNames(self,
                "QFileDialog.getOpenFileNames()", self.openFilesPath,
                "All Files (*);;Text Files (*.txt);;CSV Files (*.csv);;TSV Files (*.tsv)", "", options)
        if files:
            parser = BibleVerseParser(config.parserStandarisation)
            for file in files:
                parser.startParsing(file)
            del parser
            self.onTaggingCompleted()

    def tagFolder(self):
        options = QFileDialog.DontResolveSymlinks | QFileDialog.ShowDirsOnly
        directory = QFileDialog.getExistingDirectory(self,
                "QFileDialog.getExistingDirectory()",
                self.directoryLabel.text(), options)
        if directory:
            path, file = os.path.split(directory)
            outputFile = os.path.join(path, "output_{0}".format(file))
            BibleVerseParser(config.parserStandarisation).startParsing(directory)
            self.onTaggingCompleted()

    # Actions - hide / show tool bars
    def hideShowMainToolBar(self):
        if self.firstToolBar.isVisible():
            self.firstToolBar.hide()
        else:
            self.firstToolBar.show()

    def hideShowSecondaryToolBar(self):
        if self.secondToolBar.isVisible():
            self.secondToolBar.hide()
        else:
            self.secondToolBar.show()

    def hideShowLeftToolBar(self):
        if self.leftToolBar.isVisible():
            self.leftToolBar.hide()
        else:
            self.leftToolBar.show()

    def hideShowRightToolBar(self):
        if self.rightToolBar.isVisible():
            self.rightToolBar.hide()
        else:
            self.rightToolBar.show()

    def hideShowAdditionalToolBar(self):
        if config.singleToolBar:
            config.singleToolBar = False
        else:
            config.singleToolBar = True
        self.setAdditionalToolBar()

    def setAdditionalToolBar(self):
        self.firstToolBar.show()
        config.noToolBar = False
        if config.singleToolBar:
            self.setStudyBibleToolBar()
            self.secondToolBar.show()
            self.leftToolBar.show()
            self.rightToolBar.show()
        else:
            self.studyBibleToolBar.hide()
            self.secondToolBar.hide()
            self.leftToolBar.hide()
            self.rightToolBar.hide()

    def setNoToolBar(self):
        if config.noToolBar:
            config.noToolBar = False
            self.showAllToolBar()
        else:
            config.noToolBar = True
            self.hideAllToolBar()

    def showAllToolBar(self):
        config.singleToolBar = True
        self.firstToolBar.show()
        self.setStudyBibleToolBar()
        self.secondToolBar.show()
        self.leftToolBar.show()
        self.rightToolBar.show()

    def hideAllToolBar(self):
        config.singleToolBar = False
        self.firstToolBar.hide()
        self.studyBibleToolBar.hide()
        self.secondToolBar.hide()
        self.leftToolBar.hide()
        self.rightToolBar.hide()

    # Actions - book features
    def openBookMenu(self):
        self.runTextCommand("_book:::", False, "main")

    def displaySearchBookCommand(self):
        config.bookSearchString = ""
        self.textCommandLineEdit.setText("SEARCHBOOK:::{0}:::".format(config.book))
        self.textCommandLineEdit.setFocus()

    # Action - bible search commands
    def displaySearchBibleCommand(self):
        self.textCommandLineEdit.setText("SEARCH:::{0}:::".format(config.mainText))
        self.textCommandLineEdit.setFocus()

    def displayISearchBibleCommand(self):
        self.textCommandLineEdit.setText("iSEARCH:::{0}:::".format(config.mainText))
        self.textCommandLineEdit.setFocus()

    def displaySearchStudyBibleCommand(self):
        self.textCommandLineEdit.setText("SEARCH:::{0}:::".format(config.studyText))
        self.textCommandLineEdit.setFocus()

    def displayISearchStudyBibleCommand(self):
        self.textCommandLineEdit.setText("iSEARCH:::{0}:::".format(config.studyText))
        self.textCommandLineEdit.setFocus()

    # Action - other search commands
    def searchCommandChapterNote(self):
        self.textCommandLineEdit.setText("SEARCHCHAPTERNOTE:::")
        self.textCommandLineEdit.setFocus()

    def searchCommandVerseNote(self):
        self.textCommandLineEdit.setText("SEARCHVERSENOTE:::")
        self.textCommandLineEdit.setFocus()

    def searchCommandBibleDictionary(self):
        self.textCommandLineEdit.setText("SEARCHTOOL:::{0}:::".format(config.dictionary))
        self.textCommandLineEdit.setFocus()

    def searchCommandBibleEncyclopedia(self):
        self.textCommandLineEdit.setText("SEARCHTOOL:::{0}:::".format(config.encyclopedia))
        self.textCommandLineEdit.setFocus()

    def searchCommandBibleCharacter(self):
        self.textCommandLineEdit.setText("SEARCHTOOL:::EXLBP:::")
        self.textCommandLineEdit.setFocus()

    def searchCommandBibleName(self):
        self.textCommandLineEdit.setText("SEARCHTOOL:::HBN:::")
        self.textCommandLineEdit.setFocus()

    def searchCommandBibleLocation(self):
        self.textCommandLineEdit.setText("SEARCHTOOL:::EXLBL:::")
        self.textCommandLineEdit.setFocus()

    def searchCommandBibleTopic(self):
        self.textCommandLineEdit.setText("SEARCHTOOL:::EXLBT:::")
        self.textCommandLineEdit.setFocus()

    def searchCommandLexicon(self):
        self.textCommandLineEdit.setText("LEXICON:::")
        self.textCommandLineEdit.setFocus()

    def searchCommandThirdPartyDictionary(self):
        self.textCommandLineEdit.setText("SEARCHTHIRDDICTIONARY:::")
        self.textCommandLineEdit.setFocus()

    # Actions - open urls
    def openBibleTools(self):
        webbrowser.open("https://bibletools.app")

    def openUniqueBible(self):
        webbrowser.open("https://uniquebible.app")

    def openMarvelBible(self):
        webbrowser.open("https://marvel.bible")

    def openBibleBento(self):
        webbrowser.open("https://biblebento.com")

    def openOpenGNT(self):
        webbrowser.open("https://opengnt.com")

    def openSource(self):
        webbrowser.open("https://github.com/eliranwong/")

    def openUniqueBibleSource(self):
        webbrowser.open("https://github.com/eliranwong/UniqueBible")

    def openHebrewBibleSource(self):
        webbrowser.open("https://github.com/eliranwong/OpenHebrewBible")

    def openOpenGNTSource(self):
        webbrowser.open("https://github.com/eliranwong/OpenGNT")

    def openCredits(self):
        webbrowser.open("https://marvel.bible/resource.php")

    def contactEliranWong(self):
        webbrowser.open("https://marvel.bible/contact/contactform.php")

    # Actions - resize the main window
    def fullsizeWindow(self):
        self.resizeWindow(1, 1)

    def twoThirdWindow(self):
        self.resizeWindow(2/3, 2/3)

    def halfScreenHeight(self):
        self.resizeWindow(1, 1/2)

    def halfScreenWidth(self):
        self.resizeWindow(1/2, 1)

    def resizeWindow(self, widthFactor, heightFactor):
        availableGeometry = qApp.desktop().availableGeometry()
        self.resize(availableGeometry.width() * widthFactor, availableGeometry.height() * heightFactor)

    # Actions - enable or disable study bible / bible displayed on study view
    def getStudyBibleDisplay(self):
        if config.openBibleInMainViewOnly:
            return "addStudyViewBible.png"
        else:
            return "deleteStudyViewBible.png"

    def getStudyBibleDisplayToolTip(self):
        if config.openBibleInMainViewOnly:
            return "Enable Bible Display on Study View"
        else:
            return "Disable Bible Display on Study View"

    def enableStudyBibleButtonClicked(self):
        if config.openBibleInMainViewOnly:
            config.openBibleInMainViewOnly = False
            self.studyBibleToolBar.show()
        else:
            config.openBibleInMainViewOnly = True
            self.studyBibleToolBar.hide()
        enableStudyBibleButtonFile = os.path.join("htmlResources", self.getStudyBibleDisplay())
        self.enableStudyBibleButton.setIcon(QIcon(enableStudyBibleButtonFile))
        self.enableStudyBibleButton.setToolTip(self.getStudyBibleDisplayToolTip())

    # Actions - enable or disable lightning feature
    def getInstantInformation(self):
        if config.instantInformationEnabled:
            return "show.png"
        else:
            return "hide.png"

    def enableInstantButtonClicked(self):
        if config.instantInformationEnabled:
            config.instantInformationEnabled = False
        else:
            config.instantInformationEnabled = True
        enableInstantButtonFile = os.path.join("htmlResources", self.getInstantInformation())
        self.enableInstantButton.setIcon(QIcon(enableInstantButtonFile))

    # Actions - enable or disable paragraphs feature
    def displayBiblesInParagraphs(self):
        if config.readFormattedBibles:
            config.readFormattedBibles = False
        else:
            config.readFormattedBibles = True
        self.reloadCurrentRecord()

    def getReadFormattedBibles(self):
        if config.readFormattedBibles:
            return "paragraph.png"
        else:
            return "numbered_list.png"

    def enableParagraphButtonClicked(self):
        self.enableParagraphButtonAction(True)

    def enableParagraphButtonAction(self, display):
        if display:
            self.displayBiblesInParagraphs()
        enableParagraphButtonFile = os.path.join("htmlResources", self.getReadFormattedBibles())
        self.enableParagraphButton.setIcon(QIcon(enableParagraphButtonFile))

    # Actions - enable or disable sub-heading for plain bibles
    def getAddSubheading(self):
        if config.addTitleToPlainChapter:
            return "subheadingEnable.png"
        else:
            return "subheadingDisable.png"

    def enableSubheadingButtonClicked(self):
        if config.addTitleToPlainChapter:
            config.addTitleToPlainChapter = False
        else:
            config.addTitleToPlainChapter = True
        self.reloadCurrentRecord()
        enableSubheadingButtonFile = os.path.join("htmlResources", self.getAddSubheading())
        self.enableSubheadingButton.setIcon(QIcon(enableSubheadingButtonFile))

    # Actions - change font size
    def smallerFont(self):
        if not config.fontSize == 10:
            config.fontSize = config.fontSize - 5
            self.reloadCurrentRecord()

    def largerFont(self):
        config.fontSize = config.fontSize + 5
        self.reloadCurrentRecord()

    def reloadCurrentRecord(self):
        self.mainHistoryPage[self.mainView.currentIndex()] = True
        self.studyHistoryPage[self.studyView.currentIndex()] = True
        if config.readFormattedBibles:
            mappedBibles = (
                ("MIB", "OHGBi"),
                ("MOB", "OHGB"),
                #("LXX1", "LXX1i"),
                #("LXX2i", "LXX2"),
            )
            for view in ("main", "study"):
                textCommand = config.history[view][config.currentRecord[view]]
                for formattedBible, plainBible in mappedBibles:
                    textCommand = textCommand.replace(plainBible, formattedBible)
                    self.runTextCommand(textCommand, False, view)
        else:
            mappedBibles = (
                ("MIB", "OHGBi"),
                ("MOB", "OHGB"),
                ("MPB", "OHGB"),
                ("MTB", "OHGB"),
                ("MAB", "OHGB"),
                #("LXX1", "LXX1i"),
                #("LXX2i", "LXX2"),
            )
            for view in ("main", "study"):
                textCommand = config.history[view][config.currentRecord[view]]
                for formattedBible, plainBible in mappedBibles:
                    textCommand = textCommand.replace(formattedBible, plainBible)
                    self.runTextCommand(textCommand, False, view)
        self.mainHistoryPage[self.mainView.currentIndex()] = False
        self.studyHistoryPage[self.studyView.currentIndex()] = False

    # Actions - previous / next chapter
    def previousMainChapter(self):
        newChapter = config.mainC - 1
        biblesSqlite = BiblesSqlite()
        mainChapterList = biblesSqlite.getChapterList()
        del biblesSqlite
        if newChapter in mainChapterList:
            newTextCommand = self.bcvToVerseReference(config.mainB, newChapter, 1)
            self.textCommandChanged(newTextCommand, "main")

    def nextMainChapter(self):
        newChapter = config.mainC + 1
        biblesSqlite = BiblesSqlite()
        mainChapterList = biblesSqlite.getChapterList()
        del biblesSqlite
        if newChapter in mainChapterList:
            newTextCommand = self.bcvToVerseReference(config.mainB, newChapter, 1)
            self.textCommandChanged(newTextCommand, "main")

    def openMainChapter(self):
        newTextCommand = self.bcvToVerseReference(config.mainB, config.mainC, config.mainV)
        self.textCommandChanged(newTextCommand, "main")

    # Actions - recently opened bibles & commentary
    def mainTextMenu(self):
        newTextCommand = "_menu:::"
        self.runTextCommand(newTextCommand, False, "main")

    def studyTextMenu(self):
        newTextCommand = "_menu:::"
        self.runTextCommand(newTextCommand, False, "study")

    def mainRefButtonClicked(self):
        newTextCommand = "_menu:::{0}.{1}.{2}.{3}".format(config.mainText, config.mainB, config.mainC, config.mainV)
        self.runTextCommand(newTextCommand, False, "main")

    def studyRefButtonClicked(self):
        newTextCommand = "_menu:::{0}.{1}.{2}.{3}".format(config.studyText, config.studyB, config.studyC, config.studyV)
        self.runTextCommand(newTextCommand, False, "study")

    def commentaryRefButtonClicked(self):
        newTextCommand = "_commentary:::{0}.{1}.{2}.{3}".format(config.commentaryText, config.commentaryB, config.commentaryC, config.commentaryV)
        self.runTextCommand(newTextCommand, False, "study")

    def updateMainRefButton(self):
        self.mainTextMenuButton.setText(self.verseReference("main")[0])
        self.mainRefButton.setText(self.verseReference("main")[1])

    def updateStudyRefButton(self):
        self.studyTextMenuButton.setText(self.verseReference("study")[0])
        self.studyRefButton.setText(self.verseReference("study")[1])

    def updateCommentaryRefButton(self):
        self.commentaryRefButton.setText(self.verseReference("commentary"))

    def verseReference(self, view):
        if view == "main":
            return (config.mainText, self.bcvToVerseReference(config.mainB, config.mainC, config.mainV))
        elif view == "study":
            return (config.studyText, self.bcvToVerseReference(config.studyB, config.studyC, config.studyV))
        elif view == "commentary":
            return "{0} - {1}".format(config.commentaryText, self.bcvToVerseReference(config.commentaryB, config.commentaryC, config.commentaryV))

    # Actions - access history records
    def mainHistoryButtonClicked(self):
        self.mainView.setHtml(self.getHistory("main"), baseUrl)

    def studyHistoryButtonClicked(self):
        self.studyView.setHtml(self.getHistory("study"), baseUrl)

    def getHistory(self, view):
        if view == "main":
            self.mainHistoryPage[self.mainView.currentIndex()] = True
        elif view == "study":
            self.studyHistoryPage[self.studyView.currentIndex()] = True
        historyRecords = [(counter, record) for counter, record in enumerate(config.history[view])]
        if view == "external":
            html = "<br>".join(["<button class='feature' onclick='openExternalRecord({0})'>{1}</button> [<ref onclick='editExternalRecord({0})'>edit</ref>]".format(counter, record) for counter, record in reversed(historyRecords)])
        else:
            html = "<br>".join(["<button class='feature' onclick='openHistoryRecord({0})'>{1}</button>".format(counter, record) for counter, record in reversed(historyRecords)])
        html = self.htmlWrapper(html)
        return html

    # navigation between history records
    def openHistoryRecord(self, view, recordNumber):
        config.currentRecord[view] = recordNumber
        textCommand = config.history[view][recordNumber]
        self.runTextCommand(textCommand, False, view)
        if view == "main":
            self.textCommandLineEdit.setText(textCommand)
            self.mainHistoryPage[self.mainView.currentIndex()] = False
        elif view == "study":
            self.studyHistoryPage[self.studyView.currentIndex()] = False

    def back(self):
        mainCurrentRecord = config.currentRecord["main"]
        if not mainCurrentRecord == 0:
            mainCurrentRecord = mainCurrentRecord - 1
            self.openHistoryRecord("main", mainCurrentRecord)

    def forward(self):
        mainCurrentRecord = config.currentRecord["main"]
        if not mainCurrentRecord == (len(config.history["main"]) - 1):
            mainCurrentRecord = mainCurrentRecord + 1
            self.openHistoryRecord("main", mainCurrentRecord)

    def studyBack(self):
        if config.parallelMode == 0:
            self.parallel()
        studyCurrentRecord = config.currentRecord["study"]
        if not studyCurrentRecord == 0:
            studyCurrentRecord = studyCurrentRecord - 1
            self.openHistoryRecord("study", studyCurrentRecord)

    def studyForward(self):
        if config.parallelMode == 0:
            self.parallel()
        studyCurrentRecord = config.currentRecord["study"]
        if not studyCurrentRecord == (len(config.history["study"]) - 1):
            studyCurrentRecord = studyCurrentRecord + 1
            self.openHistoryRecord("study", studyCurrentRecord)

    # root folder for webViewEngine
    def setupBaseUrl(self):
        # baseUrl
        # External objects, such as stylesheets or images referenced in the HTML document, are located RELATIVE TO baseUrl .
        # e.g. put all local files linked by html's content in folder "htmlResources"
        global baseUrl
        relativePath = os.path.join("htmlResources", "theText.png")
        absolutePath = os.path.abspath(relativePath)
        baseUrl = QUrl.fromLocalFile(absolutePath)

    # finish view loading
    def finishMainViewLoading(self):
        # scroll to the main verse
        self.mainPage.runJavaScript("var activeVerse = document.getElementById('v"+str(config.mainB)+"."+str(config.mainC)+"."+str(config.mainV)+"'); if (typeof(activeVerse) != 'undefined' && activeVerse != null) { activeVerse.scrollIntoView(); activeVerse.style.color = 'red'; } else { document.getElementById('v0.0.0').scrollIntoView(); }")

    def finishStudyViewLoading(self):
        # scroll to the study verse
        self.studyPage.runJavaScript("var activeVerse = document.getElementById('v"+str(config.studyB)+"."+str(config.studyC)+"."+str(config.studyV)+"'); if (typeof(activeVerse) != 'undefined' && activeVerse != null) { activeVerse.scrollIntoView(); activeVerse.style.color = 'red'; } else { document.getElementById('v0.0.0').scrollIntoView(); }")

    # finish pdf printing
    def pdfPrintingFinishedAction(self, filePath, success):
        if success:
            self.openExternalFile(filePath)
        else:
            print("Failed to print pdf")

    # running specific commands
    def runFeature(self, keyword):
        mainVerseReference = self.bcvToVerseReference(config.mainB, config.mainC, config.mainV)
        newTextCommand = "{0}:::{1}".format(keyword, mainVerseReference)
        self.textCommandChanged(newTextCommand, "main")

    def runMOB(self):
        self.runFeature("BIBLE:::MOB")

    def runMIB(self):
        self.runFeature("BIBLE:::MIB")

    def runMAB(self):
        self.runFeature("BIBLE:::MAB")

    def runMPB(self):
        self.runFeature("BIBLE:::MPB")

    def runMTB(self):
        self.runFeature("BIBLE:::MTB")

    def runCOMPARE(self):
        self.runFeature("COMPARE")

    def runCROSSREFERENCE(self):
        self.runFeature("CROSSREFERENCE")

    def runTSKE(self):
        self.runFeature("TSKE")

    def runTRANSLATION(self):
        self.runFeature("TRANSLATION")

    def runDISCOURSE(self):
        self.runFeature("DISCOURSE")

    def runWORDS(self):
        self.runFeature("WORDS")

    def runCOMBO(self):
        self.runFeature("COMBO")

    def runCOMMENTARY(self):
        self.runFeature("COMMENTARY")

    def runINDEX(self):
        self.runFeature("INDEX")

    # change of unique bible commands
    def mainTextCommandChanged(self, newTextCommand):
        self.textCommandChanged(newTextCommand, "main")

    def studyTextCommandChanged(self, newTextCommand):
        self.textCommandChanged(newTextCommand, "study")

    def instantTextCommandChanged(self, newTextCommand):
        self.textCommandChanged(newTextCommand, "instant")

    # change of text command detected via change of document.title
    def textCommandChanged(self, newTextCommand, source="main"):
        exceptionTuple = ("UniqueBible.app", "about:blank", "study.html")
        if not (newTextCommand.startswith("data:text/html;") or newTextCommand.startswith("file:///") or newTextCommand[-4:] == ".txt" or newTextCommand in exceptionTuple):
            if source == "main" and not newTextCommand.startswith("_"):
                self.textCommandLineEdit.setText(newTextCommand)
            if newTextCommand.startswith("_"):
                self.runTextCommand(newTextCommand, False, source)
            else:
                self.runTextCommand(newTextCommand, True, source)

    # change of text command detected via user input
    def textCommandEntered(self, source="main"):
        newTextCommand = self.textCommandLineEdit.text()
        self.runTextCommand(newTextCommand, True, source)

    def runTextCommand(self, textCommand, addRecord=True, source="main"):
        view, content = self.textCommandParser.parser(textCommand, source)

        if content == "INVALID_COMMAND_ENTERED":
            self.mainPage.runJavaScript("alert('Invalid command not processed.')")
        elif view == "":
            if source == "main":
                self.mainPage.runJavaScript("document.title = 'UniqueBible.app';")
            elif source == "study":
                self.studyPage.runJavaScript("document.title = 'UniqueBible.app';")
        elif view == "command":
            self.textCommandLineEdit.setText(content)
            self.textCommandLineEdit.setFocus()
        else:
            activeBCVsettings = ""
            if view == "main":
                activeBCVsettings = "<script>var activeText = '{0}'; var activeB = {1}; var activeC = {2}; var activeV = {3};</script>".format(config.mainText, config.mainB, config.mainC, config.mainV)
            elif view == "study":
                activeBCVsettings = "<script>var activeText = '{0}'; var activeB = {1}; var activeC = {2}; var activeV = {3};</script>".format(config.studyText, config.studyB, config.studyC, config.studyV)
            html = "<!DOCTYPE html><html><head><title>UniqueBible.app</title><link rel='stylesheet' type='text/css' href='theText.css'><script src='theText.js'></script><script src='w3.js'></script>{0}<script>var versionList = []; var compareList = []; var parallelList = [];</script></head><body style='font-size: {1}%;'><span id='v0.0.0'></span>{2}</body></html>".format(activeBCVsettings, config.fontSize, content)
            views = {
                "main": self.mainView,
                "study": self.studyView,
                "instant": self.instantView,
            }
            # final touch to transform text HERE
            searchReplace = (
                ('onclick=[{0}"]bcv\(([0-9]+?),[ ]*?([0-9]+?),[ ]*?([0-9]+?)\)[{0}"]'.format("'"), r'onclick="bcv(\1,\2,\3)" onmouseover="imv(\1,\2,\3)"'),
                ('onclick=[{0}"]cr\(([0-9]+?),[ ]*?([0-9]+?),[ ]*?([0-9]+?)\)[{0}"]'.format("'"), self.convertCrLink),
            )
            for search, replace in searchReplace:
                html = re.sub(search, replace, html)
            # load into widget view
            if view == "study":
                # save html in a separate file if text is larger than 2MB
                # reason: setHTML does not work with content larger than 2MB
                newCommand = (self.studyView.currentIndex(), textCommand)
                if self.studyHistoryPage[self.studyView.currentIndex()] or self.lastLoadedCommand[view] != newCommand:
                    self.openTextOnStudyView(html)
                    self.lastLoadedCommand["study"] = newCommand
            elif view == "main":
                # save html in a separate file if text is larger than 2MB
                # reason: setHTML does not work with content larger than 2MB
                newCommand = (self.mainView.currentIndex(), textCommand)
                if self.mainHistoryPage[self.mainView.currentIndex()] or self.lastLoadedCommand[view] != newCommand:
                    self.openTextOnMainView(html)
                    self.lastLoadedCommand["main"] = newCommand
            elif view.startswith("popover"):
                view = view.split(".")[1]
                views[view].currentWidget().openPopover(html=html)
            else:
                views[view].setHtml(html, baseUrl)
            if addRecord == True and view in ("main", "study"):
                self.addHistoryRecord(view, textCommand)

    def convertCrLink(self, match):
        value = match.group()
        bookNo = Converter().convertMyBibleBookNo(int(re.sub('onclick=[{0}"]cr\(([0-9]+?),[ ]*?[0-9]+?,[ ]*?[0-9]+?\)[{0}"]'.format("'"), r'\1', value)))
        return re.sub('onclick=[{0}"]cr\([0-9]+?,[ ]*?([0-9]+?),[ ]*?([0-9]+?)\)[{0}"]'.format("'"), r'onclick="bcv({0},\1,\2)" onmouseover="imv({0},\1,\2)"'.format(bookNo), value)

    # add a history record
    def addHistoryRecord(self, view, textCommand):
        if not textCommand.startswith("_"):
            viewhistory = config.history[view]
            if not (viewhistory[-1] == textCommand):
                viewhistory.append(textCommand)
                # set maximum number of history records for each view here
                historyRecordAllowed = config.historyRecordAllowed
                if len(viewhistory) > historyRecordAllowed:
                    viewhistory = viewhistory[-historyRecordAllowed:]
                config.history[view] = viewhistory
                config.currentRecord[view] = len(viewhistory) - 1

    # switch between landscape / portrait mode
    def switchIconSize(self):
        if config.toolBarIconFullSize:
            config.toolBarIconFullSize = False
        else:
            config.toolBarIconFullSize = True
        self.mainPage.runJavaScript('alert("Icon size is changed. You need to restart the app to apply the changes.")')

    # switch between landscape / portrait mode
    def switchLandscapeMode(self):
        if config.landscapeMode:
            config.landscapeMode = False
        else:
            config.landscapeMode = True
        self.centralWidget.switchLandscapeMode()
        self.resizeParallel()
        self.resizeInstant()

    # Actions - hide / show / resize study & lightning views
    def instant(self):
        if config.instantMode == 0:
            config.instantMode = 1
        elif config.instantMode == 1:
            config.instantMode = 0
        self.resizeInstant()

    def resizeInstant(self):
        if config.landscapeMode:
            self.resizeInstantL()
        else:
            self.resizeInstantP()

    def resizeInstantL(self):
        instantRatio = {
            0: (10, 0, 0),
            1: (10, 0, 2),
        }
        top, middle, bottom = instantRatio[config.instantMode]
        self.centralWidget.layout.setRowStretch(0, top)
        self.centralWidget.layout.setRowStretch(1, middle)
        self.centralWidget.layout.setRowStretch(2, bottom)
        if config.instantMode:
            self.instantView.show()
        else:
            self.instantView.hide()

    def resizeInstantP(self):
        instantRatio = {
            (0, 0): (10, 0, 0),
            (0, 1): (10, 5, 0),
            (0, 2): (5, 5, 0),
            (0, 3): (5, 10, 0),
            (1, 0): (10, 0, 2),
            (1, 1): (10, 5, 3),
            (1, 2): (5, 5, 2),
            (1, 3): (5, 10, 3),
        }
        top, middle, bottom = instantRatio[(config.instantMode, config.parallelMode)]
        self.centralWidget.layout.setRowStretch(0, top)
        self.centralWidget.layout.setRowStretch(1, middle)
        self.centralWidget.layout.setRowStretch(2, bottom)
        if config.instantMode:
            self.instantView.show()
        else:
            self.instantView.hide()

    def parallel(self):
        if config.parallelMode == 3:
            config.parallelMode = 0
        else:
            config.parallelMode += 1
        self.resizeParallel()

    def resizeParallel(self):
        if config.landscapeMode:
            self.resizeParallelL()
        else:
            self.resizeParallelP()

    def resizeParallelL(self):
        parallelRatio = {
            0: (1, 0),
            1: (2, 1),
            2: (1, 1),
            3: (1, 2),
        }
        left, right = parallelRatio[config.parallelMode]
        self.centralWidget.layout.setColumnStretch(0, left)
        self.centralWidget.layout.setColumnStretch(1, right)
        if config.parallelMode:
            self.studyView.show()
        else:
            self.studyView.hide()

    def resizeParallelP(self):
        parallelRatio = {
            (0, 0): (10, 0, 0),
            (0, 1): (10, 5, 0),
            (0, 2): (5, 5, 0),
            (0, 3): (5, 10, 0),
            (1, 0): (10, 0, 2),
            (1, 1): (10, 5, 3),
            (1, 2): (5, 5, 2),
            (1, 3): (5, 10, 3),
        }
        top, middle, bottom = parallelRatio[(config.instantMode, config.parallelMode)]
        self.centralWidget.layout.setRowStretch(0, top)
        self.centralWidget.layout.setRowStretch(1, middle)
        self.centralWidget.layout.setRowStretch(2, bottom)
        if config.parallelMode:
            self.studyView.show()
        else:
            self.studyView.hide()


class CentralWidget(QWidget):

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        #self.html = "<h1>UniqueBible.app</h1><p>This is '<b>Main View</b>'.</p>"

        #self.mainView = WebEngineView(self, "main")
        #self.mainView.setHtml(self.html, baseUrl)
        #self.studyView = WebEngineView(self, "study")
        #self.studyView.setHtml("This is '<b>Study View</b>'.", baseUrl)

        self.mainView = TabWidget(self, "main")
        self.parent.mainView = self.mainView
        for i in range(config.numberOfTab):
            self.mainView.addTab(WebEngineView(self, "main"), "Bible{0}".format(i+1))

        self.studyView = TabWidget(self, "study")
        self.parent.studyView = self.studyView
        for i in range(config.numberOfTab):
            self.studyView.addTab(WebEngineView(self, "study"), "Tool{0}".format(i+1))

        self.instantView = WebEngineView(self, "instant")
        self.instantView.setHtml("<u><b>Bottom View</b></u><br>It is designed for displaying instant information, with mouse hovering over verse numbers, tagged words or links.", baseUrl)

        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 10, 0, 3)
        self.layout.setHorizontalSpacing(0)
        self.layout.setVerticalSpacing(2)
        self.addWidgetToLayout()
        self.setLayout(self.layout)

    def switchLandscapeMode(self):
        for widget in (self.mainView, self.studyView, self.instantView):
            self.layout.removeWidget(widget)
        self.addWidgetToLayout()

    def addWidgetToLayout(self):
        if config.landscapeMode:
            self.addWidgetLandscape()
        else:
            self.addWidgetPortrait()

    def addWidgetLandscape(self):
        self.layout.addWidget(self.mainView, 0, 0)
        self.layout.addWidget(self.studyView, 0, 1)
        self.layout.addWidget(self.instantView, 2, 0, 1, 2)

    def addWidgetPortrait(self):
        self.layout.addWidget(self.mainView, 0, 0, 1, 2)
        self.layout.addWidget(self.studyView, 1, 0, 1, 2)
        self.layout.addWidget(self.instantView, 2, 0, 1, 2)


class TabWidget(QTabWidget):

    def __init__(self, parent, name):
        super().__init__()
        self.parent = parent
        self.name = name
        self.currentChanged.connect(self.tabSelected)
        # notes:
        # the first tab is indexed with 0.  the rest with 1,2,3,4,etc.
        # to get the index of current tab, print(self.currentIndex())
        # to change the current tab, self.setCurrentWidget(self.widget(4))

    def setHtml(self, html, baseUrl):
        self.currentWidget().setHtml(html, baseUrl)

    def load(self, path):
        self.currentWidget().load(path)

    def tabSelected(self):
        if self.name == "main":
            self.parent.parent.setMainPage()
        elif self.name == "study":
            self.parent.parent.setStudyPage()


class WebEngineView(QWebEngineView):

    def __init__(self, parent, name):
        super().__init__()
        self.parent = parent
        self.name = name
        
        # add context menu (triggered by right-clicking)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.selectionChanged.connect(self.updateContextMenu)
        self.addMenuActions()

    def updateContextMenu(self):
        text = self.getText()
        parser = BibleVerseParser(config.parserStandarisation)
        book = parser.bcvToVerseReference(self.getBook(), 1, 1)[:-4]
        del parser
        self.searchText.setText("Search in {0}".format(text))
        self.searchTextInBook.setText("Search in {0} > {1}".format(text, book))
        self.iSearchText.setText("Search with {1} in {0}".format(text, config.iSearchVersion))
        self.iSearchTextInBook.setText("Search with {2} in {0} > {1}".format(text, book, config.iSearchVersion))
        self.searchBibleTopic.setText("Bible Topic > {0}".format(config.topic))
        self.searchBibleDictionary.setText("Bible Dictionary > {0}".format(config.dictionary))
        self.searchBibleEncyclopedia.setText("Bible Encyclopedia > {0}".format(config.encyclopedia))
        self.searchThirdDictionary.setText("3rd Party Dictionary > {0}".format(config.thirdDictionary))

    def getText(self):
        text = {
            "main": config.mainText,
            "study": config.studyText,
            "instant": config.mainText,
        }
        return text[self.name]

    def getBook(self):
        book = {
            "main": config.mainB,
            "study": config.studyB,
            "instant": config.mainB,
        }
        return book[self.name]

    def addMenuActions(self):
        copyText = QAction(self)
        copyText.setText("Copy")
        copyText.triggered.connect(self.copySelectedText)
        self.addAction(copyText)

        tts = QAction(self)
        tts.setText("Speak")
        tts.triggered.connect(self.textToSpeech)
        self.addAction(tts)

        self.searchText = QAction(self)
        self.searchText.setText("Search")
        self.searchText.triggered.connect(self.searchSelectedText)
        self.addAction(self.searchText)

        self.searchTextInBook = QAction(self)
        self.searchTextInBook.setText("Search in Current Book")
        self.searchTextInBook.triggered.connect(self.searchSelectedTextInBook)
        self.addAction(self.searchTextInBook)

        self.iSearchText = QAction(self)
        self.iSearchText.setText("Search with {0}".format(config.iSearchVersion))
        self.iSearchText.triggered.connect(self.iSearchSelectedText)
        self.addAction(self.iSearchText)

        self.iSearchTextInBook = QAction(self)
        self.iSearchTextInBook.setText("Search with {0} in Current Book".format(config.iSearchVersion))
        self.iSearchTextInBook.triggered.connect(self.iSearchSelectedTextInBook)
        self.addAction(self.iSearchTextInBook)

        self.searchLexicon = QAction(self)
        self.searchLexicon.setText("Hebrew / Greek Lexicons")
        self.searchLexicon.triggered.connect(self.searchHebrewGreekLexicon)
        self.addAction(self.searchLexicon)

        searchBibleCharacter = QAction(self)
        searchBibleCharacter.setText("Bible Character")
        searchBibleCharacter.triggered.connect(self.searchCharacter)
        self.addAction(searchBibleCharacter)

        searchBibleName = QAction(self)
        searchBibleName.setText("Bible Name")
        searchBibleName.triggered.connect(self.searchName)
        self.addAction(searchBibleName)

        searchBibleLocation = QAction(self)
        searchBibleLocation.setText("Bible Location")
        searchBibleLocation.triggered.connect(self.searchLocation)
        self.addAction(searchBibleLocation)

        self.searchBibleTopic = QAction(self)
        self.searchBibleTopic.setText("Bible Topic")
        self.searchBibleTopic.triggered.connect(self.searchTopic)
        self.addAction(self.searchBibleTopic)

        self.searchBibleEncyclopedia = QAction(self)
        self.searchBibleEncyclopedia.setText("Bible Encyclopedia")
        self.searchBibleEncyclopedia.triggered.connect(self.searchEncyclopedia)
        self.addAction(self.searchBibleEncyclopedia)

        self.searchBibleDictionary = QAction(self)
        self.searchBibleDictionary.setText("Bible Dictionary")
        self.searchBibleDictionary.triggered.connect(self.searchDictionary)
        self.addAction(self.searchBibleDictionary)

        self.searchThirdDictionary = QAction(self)
        self.searchThirdDictionary.setText("3rd Party Dictionary")
        self.searchThirdDictionary.triggered.connect(self.searchThirdPartyDictionary)
        self.addAction(self.searchThirdDictionary)

        searchBibleReferences = QAction(self)
        searchBibleReferences.setText("Extract All Bible References")
        searchBibleReferences.triggered.connect(self.extractAllReferences)
        self.addAction(searchBibleReferences)

        runAsCommandLine = QAction(self)
        runAsCommandLine.setText("Run as Command")
        runAsCommandLine.triggered.connect(self.runAsCommand)
        self.addAction(runAsCommandLine)

    def messageNoSelection(self):
        self.page().runJavaScript("alert('You have not selected word(s) for this action!')")

    def messageNoTtsEngine(self):
        self.page().runJavaScript("alert('No text-to-speech engine is found in your device!')")

    def messageNoTtsVoice(self):
        self.page().runJavaScript("alert('No text-to-speech voice is found in your device!')")

    def copySelectedText(self):
        if not self.selectedText():
            self.messageNoSelection()
        else:
            self.page().triggerAction(self.page().Copy)

    def textToSpeech(self):
        if not self.selectedText():
            self.messageNoSelection()
        else:
            engineNames = QTextToSpeech.availableEngines()
            if engineNames:
                self.engine = QTextToSpeech(engineNames[0])
                engineVoices = self.engine.availableVoices()
                if engineVoices:
                    self.engine.setVoice(engineVoices[0])
                    self.engine.setVolume(1.0)
                    self.engine.say(self.selectedText())
                else:
                    self.messageNoTtsVoice()
            else:
                self.messageNoTtsEngine()

    def searchSelectedText(self):
        selectedText = self.selectedText()
        if not selectedText:
            self.messageNoSelection()
        else:
            searchCommand = "SEARCH:::{0}:::{1}".format(self.getText(), selectedText)
            self.parent.parent.textCommandChanged(searchCommand, self.name)

    def searchSelectedTextInBook(self):
        selectedText = self.selectedText()
        if not selectedText:
            self.messageNoSelection()
        else:
            searchCommand = "ADVANCEDSEARCH:::{0}:::Book = {1} AND Scripture LIKE '%{2}%'".format(self.getText(), self.getBook(), selectedText)
            self.parent.parent.textCommandChanged(searchCommand, self.name)

    def iSearchSelectedText(self):
        selectedText = self.selectedText()
        if not selectedText:
            self.messageNoSelection()
        else:
            searchCommand = "ISEARCH:::{0}:::{1}".format(self.getText(), selectedText)
            self.parent.parent.textCommandChanged(searchCommand, self.name)

    def iSearchSelectedTextInBook(self):
        selectedText = self.selectedText()
        if not selectedText:
            self.messageNoSelection()
        else:
            searchCommand = "ADVANCEDISEARCH:::{0}:::Book = {1} AND Scripture LIKE '%{2}%'".format(self.getText(), self.getBook(), selectedText)
            self.parent.parent.textCommandChanged(searchCommand, self.name)

    def searchHebrewGreekLexicon(self):
        selectedText = self.selectedText()
        if not selectedText:
            self.messageNoSelection()
        else:
            searchCommand = "LEXICON:::{0}".format(selectedText)
            self.parent.parent.textCommandChanged(searchCommand, self.name)

    def searchResource(self, module):
        selectedText = self.selectedText()
        if not selectedText:
            self.messageNoSelection()
        else:
            searchCommand = "SEARCHTOOL:::{0}:::{1}".format(module, selectedText)
            self.parent.parent.textCommandChanged(searchCommand, self.name)

    def searchCharacter(self):
        self.searchResource("EXLBP")

    def searchName(self):
        self.searchResource("HBN")

    def searchLocation(self):
        self.searchResource("EXLBL")

    def searchTopic(self):
        self.searchResource(config.topic)

    def searchDictionary(self):
        self.searchResource(config.dictionary)

    def searchEncyclopedia(self):
        self.searchResource(config.encyclopedia)

    def searchThirdPartyDictionary(self):
        selectedText = self.selectedText()
        if not selectedText:
            self.messageNoSelection()
        else:
            searchCommand = "SEARCHTHIRDDICTIONARY:::{0}:::{1}".format(config.thirdDictionary, selectedText)
            self.parent.parent.textCommandChanged(searchCommand, self.name)

    def extractAllReferences(self):
        selectedText = self.selectedText()
        parser = BibleVerseParser(config.parserStandarisation)
        verseList = parser.extractAllReferences(selectedText, False, True)
        del parser
        if not verseList:
            self.page().runJavaScript("alert('No bible verse reference is found from the text you selected.')")
        else:
            biblesSqlite = BiblesSqlite()
            verses = biblesSqlite.readMultipleVerses(self.getText(), verseList)
            del biblesSqlite
            self.openPopover(html=verses)

    def runAsCommand(self):
        selectedText = self.selectedText()
        self.parent.parent.textCommandChanged(selectedText, "main")

    def createWindow(self, windowType):
        if windowType == QWebEnginePage.WebBrowserWindow or windowType == QWebEnginePage.WebBrowserTab:
            self.openPopover()
        return super().createWindow(windowType)

    def openPopover(self, name="popover", html="UniqueBible.app"):
        html = "<!DOCTYPE html><html><head><title>UniqueBible.app</title><link rel='stylesheet' type='text/css' href='theText.css'><script src='theText.js'></script><script src='w3.js'></script><script>var versionList = []; var compareList = []; var parallelList = [];</script></head><body style='font-size: {0}%;'><span id='v0.0.0'></span>{1}</body></html>".format(config.fontSize, html)
        self.popoverView = WebEngineViewPopover(self, name, self.name)
        self.popoverView.setHtml(html, baseUrl)
        self.popoverView.show()


class WebEngineViewPopover(QWebEngineView):

    def __init__(self, parent, name, source):
        super().__init__()
        self.parent = parent
        self.name = name
        self.source = source
        self.setWindowTitle("Unique Bible App - Popover")
        self.titleChanged.connect(self.popoverTextCommandChanged)

        # add context menu (triggered by right-clicking)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.addMenuActions()

    def popoverTextCommandChanged(self, newTextCommand):
        self.parent.parent.parent.textCommandChanged(newTextCommand, self.source)

    def addMenuActions(self):
        copyText = QAction(self)
        copyText.setText("Copy")
        copyText.triggered.connect(self.copySelectedText)
        self.addAction(copyText)

        runAsCommandLine = QAction(self)
        runAsCommandLine.setText("Run as Command")
        runAsCommandLine.triggered.connect(self.runAsCommand)
        self.addAction(runAsCommandLine)

    def messageNoSelection(self):
        self.page().runJavaScript("alert('You have not selected word(s) for this action!')")

    def copySelectedText(self):
        if not self.selectedText():
            self.messageNoSelection()
        else:
            self.page().triggerAction(self.page().Copy)

    def runAsCommand(self):
        selectedText = self.selectedText()
        self.parent.parent.parent.textCommandChanged(selectedText, "main")


class NoteEditor(QMainWindow):

    def __init__(self, parent, noteType, noteFileName=""):
        super().__init__()
        self.parent, self.noteType = parent, noteType
        self.noteFileName = noteFileName

        # default - "Rich" mode for editing
        self.html = True
        # default - show toolbar with formatting items
        self.showToolBar = True
        # default - text is not modified; no need for saving new content
        self.parent.noteSaved = True

        # specify window size
        self.resizeWindow(2/3, 2/3)

        # setup interface
        self.setupMenuBar()
        self.addToolBarBreak()
        self.setupToolBar()
        self.setupLayout()

        # display content when first launched
        self.displayInitialContent()

        # specify window title
        self.updateWindowTitle()

    # re-implementing close event, when users close this widget
    def closeEvent(self, event):
        if self.parent.noteSaved:
            event.accept()
        else:
            if self.parent.warningNotSaved():
                self.parent.noteSaved = True
                event.accept()
            else:
                event.ignore()

    # re-implement keyPressEvent, control+S for saving file
    def keyPressEvent(self, event):
        keys = {
            Qt.Key_O: self.openFileDialog,
            Qt.Key_S: self.saveNote,
            Qt.Key_B: self.format_bold,
            Qt.Key_I: self.format_italic,
            Qt.Key_U: self.format_underline,
            Qt.Key_M: self.format_custom,
            Qt.Key_D: self.format_clear,
            Qt.Key_F: self.focusSearchField,
        }
        key = event.key()
        if event.modifiers() == Qt.ControlModifier and key in keys:
            keys[key]()

    # window appearance
    def resizeWindow(self, widthFactor, heightFactor):
        availableGeometry = qApp.desktop().availableGeometry()
        self.resize(availableGeometry.width() * widthFactor, availableGeometry.height() * heightFactor)

    def updateWindowTitle(self):
        if self.noteType == "file":
            if self.noteFileName:
                *_, title = os.path.split(self.noteFileName)
            else:
                title = "NEW"
        else:
            title = self.parent.bcvToVerseReference(self.b, self.c, self.v)
            if self.noteType == "chapter":
                title, *_ = title.split(":")
        mode = {True: "rich", False: "plain"}
        notModified = {True: "", False: " [modified]"}
        self.setWindowTitle("Note Editor ({1} mode) - {0}{2}".format(title, mode[self.html], notModified[self.parent.noteSaved]))

    # switching between "rich" & "plain" mode
    def switchMode(self):
        if self.html:
            note = self.editor.toHtml()
            self.editor.setPlainText(note)
            self.html = False
            self.updateWindowTitle()
        else:
            note = self.editor.toPlainText()
            self.editor.setHtml(note)
            self.html = True
            self.updateWindowTitle()
        # without this hide / show command below, QTextEdit does not update the text in some devices
        self.hide()
        self.show()

    def setupMenuBar(self):
        if config.toolBarIconFullSize:
            self.setupMenuBarFullIconSize()
        else:
            self.setupMenuBarStandardIconSize()

    def setupMenuBarStandardIconSize(self):

        self.menuBar = QToolBar()
        self.menuBar.setWindowTitle("Note Editor Menu Bar")
        self.menuBar.setContextMenuPolicy(Qt.PreventContextMenu)
        # In QWidget, self.menuBar is treated as the menubar without the following line
        # In QMainWindow, the following line adds the configured QToolBar as part of the toolbar of the main window
        self.addToolBar(self.menuBar)

        newButton = QPushButton()
        newButton.setToolTip("Create a New Topical Note \n[Shortcut: Ctrl/Cmd + N]")
        newButtonFile = os.path.join("htmlResources", "newfile.png")
        newButton.setIcon(QIcon(newButtonFile))
        newButton.clicked.connect(self.newNoteFile)
        self.menuBar.addWidget(newButton)

        openButton = QPushButton()
        openButton.setToolTip("Open Topical Notes \n[Shortcut: Ctrl/Cmd + O]")
        openButtonFile = os.path.join("htmlResources", "open.png")
        openButton.setIcon(QIcon(openButtonFile))
        openButton.clicked.connect(self.openFileDialog)
        self.menuBar.addWidget(openButton)

        self.menuBar.addSeparator()

        saveButton = QPushButton()
        saveButton.setToolTip("Save \n[Shortcut: Ctrl/Cmd + S]")
        saveButtonFile = os.path.join("htmlResources", "save.png")
        saveButton.setIcon(QIcon(saveButtonFile))
        saveButton.clicked.connect(self.saveNote)
        self.menuBar.addWidget(saveButton)

        saveAsButton = QPushButton()
        saveAsButton.setToolTip("Save as")
        saveAsButtonFile = os.path.join("htmlResources", "saveas.png")
        saveAsButton.setIcon(QIcon(saveAsButtonFile))
        saveAsButton.clicked.connect(self.openSaveAsDialog)
        self.menuBar.addWidget(saveAsButton)

        self.menuBar.addSeparator()

        toolBarButton = QPushButton()
        toolBarButton.setToolTip("Print")
        toolBarButtonFile = os.path.join("htmlResources", "print.png")
        toolBarButton.setIcon(QIcon(toolBarButtonFile))
        toolBarButton.clicked.connect(self.printNote)
        self.menuBar.addWidget(toolBarButton)

        self.menuBar.addSeparator()

        toolBarButton = QPushButton()
        toolBarButton.setToolTip("Show / Hide Toolbar")
        toolBarButtonFile = os.path.join("htmlResources", "toolbar.png")
        toolBarButton.setIcon(QIcon(toolBarButtonFile))
        toolBarButton.clicked.connect(self.toogleToolbar)
        self.menuBar.addWidget(toolBarButton)

        self.menuBar.addSeparator()

        switchButton = QPushButton()
        switchButton.setToolTip("Rich / Plain Mode")
        switchButtonFile = os.path.join("htmlResources", "switch.png")
        switchButton.setIcon(QIcon(switchButtonFile))
        switchButton.clicked.connect(self.switchMode)
        self.menuBar.addWidget(switchButton)

        self.menuBar.addSeparator()

        decreaseFontSizeButton = QPushButton()
        decreaseFontSizeButton.setToolTip("Smaller Font Size")
        decreaseFontSizeButtonFile = os.path.join("htmlResources", "fontMinus.png")
        decreaseFontSizeButton.setIcon(QIcon(decreaseFontSizeButtonFile))
        decreaseFontSizeButton.clicked.connect(self.decreaseNoteEditorFontSize)
        self.menuBar.addWidget(decreaseFontSizeButton)

        increaseFontSizeButton = QPushButton()
        increaseFontSizeButton.setToolTip("Larger Font Size")
        increaseFontSizeButtonFile = os.path.join("htmlResources", "fontPlus.png")
        increaseFontSizeButton.setIcon(QIcon(increaseFontSizeButtonFile))
        increaseFontSizeButton.clicked.connect(self.increaseNoteEditorFontSize)
        self.menuBar.addWidget(increaseFontSizeButton)

        self.menuBar.addSeparator()

        self.searchLineEdit = QLineEdit()
        self.searchLineEdit.setToolTip("Quick Search \n[Shortcut: Ctrl/Cmd + F]")
        self.searchLineEdit.setMaximumWidth(300)
        self.searchLineEdit.returnPressed.connect(self.searchLineEntered)
        self.menuBar.addWidget(self.searchLineEdit)

        self.menuBar.addSeparator()

    def setupMenuBarFullIconSize(self):

        self.menuBar = QToolBar()
        self.menuBar.setWindowTitle("Note Editor Menu Bar")
        self.menuBar.setContextMenuPolicy(Qt.PreventContextMenu)
        # In QWidget, self.menuBar is treated as the menubar without the following line
        # In QMainWindow, the following line adds the configured QToolBar as part of the toolbar of the main window
        self.addToolBar(self.menuBar)

        iconFile = os.path.join("htmlResources", "newfile.png")
        self.menuBar.addAction(QIcon(iconFile), "Create a New Topical Note \n[Shortcut: Ctrl/Cmd + N]", self.newNoteFile)

        iconFile = os.path.join("htmlResources", "open.png")
        self.menuBar.addAction(QIcon(iconFile), "Open Topical Notes \n[Shortcut: Ctrl/Cmd + O]", self.openFileDialog)

        self.menuBar.addSeparator()

        iconFile = os.path.join("htmlResources", "save.png")
        self.menuBar.addAction(QIcon(iconFile), "Save \n[Shortcut: Ctrl/Cmd + S]", self.saveNote)

        iconFile = os.path.join("htmlResources", "saveas.png")
        self.menuBar.addAction(QIcon(iconFile), "Save as", self.openSaveAsDialog)

        self.menuBar.addSeparator()

        iconFile = os.path.join("htmlResources", "print.png")
        self.menuBar.addAction(QIcon(iconFile), "Print", self.printNote)

        self.menuBar.addSeparator()

        iconFile = os.path.join("htmlResources", "toolbar.png")
        self.menuBar.addAction(QIcon(iconFile), "Show / Hide Toolbar", self.toogleToolbar)

        self.menuBar.addSeparator()

        iconFile = os.path.join("htmlResources", "switch.png")
        self.menuBar.addAction(QIcon(iconFile), "Rich / Plain Mode", self.switchMode)

        self.menuBar.addSeparator()

        iconFile = os.path.join("htmlResources", "fontMinus.png")
        self.menuBar.addAction(QIcon(iconFile), "Smaller Font Size", self.decreaseNoteEditorFontSize)

        iconFile = os.path.join("htmlResources", "fontPlus.png")
        self.menuBar.addAction(QIcon(iconFile), "Larger Font Size", self.increaseNoteEditorFontSize)

        self.menuBar.addSeparator()

        self.searchLineEdit = QLineEdit()
        self.searchLineEdit.setToolTip("Quick Search \n[Shortcut: Ctrl/Cmd + F]")
        self.searchLineEdit.setMaximumWidth(300)
        self.searchLineEdit.returnPressed.connect(self.searchLineEntered)
        self.menuBar.addWidget(self.searchLineEdit)

        self.menuBar.addSeparator()

    def toogleToolbar(self):
        if self.showToolBar:
            self.toolBar.hide()
            self.showToolBar = False
        else:
            self.toolBar.show()
            self.showToolBar = True

    def printNote(self):
        #document = QTextDocument("Sample Page")
        document = self.editor.document()
        printer = QPrinter()
  
        myPrintDialog = QPrintDialog(printer, self)
        if myPrintDialog.exec_() == QDialog.Accepted:
            return document.print_(printer)

    def setupToolBar(self):
        if config.toolBarIconFullSize:
            self.setupToolBarFullIconSize()
        else:
            self.setupToolBarStandardIconSize()

    def setupToolBarStandardIconSize(self):

        self.toolBar = QToolBar()
        self.toolBar.setWindowTitle("Tool Bar")
        self.toolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        # self.toolBar can be treated as an individual widget and positioned with a specified layout
        # In QMainWindow, the following line adds the configured QToolBar as part of the toolbar of the main window
        self.addToolBar(self.toolBar)

        boldButton = QPushButton()
        boldButton.setToolTip("Bold \n[Shortcut: Ctrl/Cmd + B]")
        boldButtonFile = os.path.join("htmlResources", "bold.png")
        boldButton.setIcon(QIcon(boldButtonFile))
        boldButton.clicked.connect(self.format_bold)
        self.toolBar.addWidget(boldButton)

        italicButton = QPushButton()
        italicButton.setToolTip("Italic \n[Shortcut: Ctrl/Cmd + I]")
        italicButtonFile = os.path.join("htmlResources", "italic.png")
        italicButton.setIcon(QIcon(italicButtonFile))
        italicButton.clicked.connect(self.format_italic)
        self.toolBar.addWidget(italicButton)

        underlineButton = QPushButton()
        underlineButton.setToolTip("Underline \n[Shortcut: Ctrl/Cmd + U]")
        underlineButtonFile = os.path.join("htmlResources", "underline.png")
        underlineButton.setIcon(QIcon(underlineButtonFile))
        underlineButton.clicked.connect(self.format_underline)
        self.toolBar.addWidget(underlineButton)

        self.toolBar.addSeparator()

        customButton = QPushButton()
        customButton.setToolTip("Transform Selected Text: \n[Shortcut: Ctrl/Cmd + M] \n \nBullet List, e.g.: \n* bullet one \n* bullet two \n \nNumbered List, e.g.: \n*1 numbered item one \n*2 numbered item two \n \nTable, e.g.: \n{one|two|three} \n{four|five|six}")
        customButtonFile = os.path.join("htmlResources", "custom.png")
        customButton.setIcon(QIcon(customButtonFile))
        customButton.clicked.connect(self.format_custom)
        self.toolBar.addWidget(customButton)

        self.toolBar.addSeparator()

        leftButton = QPushButton()
        leftButton.setToolTip("Align Left")
        leftButtonFile = os.path.join("htmlResources", "align_left.png")
        leftButton.setIcon(QIcon(leftButtonFile))
        leftButton.clicked.connect(self.format_left)
        self.toolBar.addWidget(leftButton)

        centerButton = QPushButton()
        centerButton.setToolTip("Center Text")
        centerButtonFile = os.path.join("htmlResources", "align_center.png")
        centerButton.setIcon(QIcon(centerButtonFile))
        centerButton.clicked.connect(self.format_center)
        self.toolBar.addWidget(centerButton)

        rightButton = QPushButton()
        rightButton.setToolTip("Align Right")
        rightButtonFile = os.path.join("htmlResources", "align_right.png")
        rightButton.setIcon(QIcon(rightButtonFile))
        rightButton.clicked.connect(self.format_right)
        self.toolBar.addWidget(rightButton)

        justifyButton = QPushButton()
        justifyButton.setToolTip("Justify")
        justifyButtonFile = os.path.join("htmlResources", "align_justify.png")
        justifyButton.setIcon(QIcon(justifyButtonFile))
        justifyButton.clicked.connect(self.format_justify)
        self.toolBar.addWidget(justifyButton)

        self.toolBar.addSeparator()

        clearButton = QPushButton()
        clearButton.setToolTip("Delete Formatting \n[Shortcut: Ctrl/Cmd + D]")
        clearButtonFile = os.path.join("htmlResources", "clearFormat.png")
        clearButton.setIcon(QIcon(clearButtonFile))
        clearButton.clicked.connect(self.format_clear)
        self.toolBar.addWidget(clearButton)

        self.toolBar.addSeparator()

        hyperlinkButton = QPushButton()
        hyperlinkButton.setToolTip("Add a Hyperlink")
        hyperlinkButtonFile = os.path.join("htmlResources", "hyperlink.png")
        hyperlinkButton.setIcon(QIcon(hyperlinkButtonFile))
        hyperlinkButton.clicked.connect(self.openHyperlinkDialog)
        self.toolBar.addWidget(hyperlinkButton)

        imageButton = QPushButton()
        imageButton.setToolTip("Add an Image")
        imageButtonFile = os.path.join("htmlResources", "gallery.png")
        imageButton.setIcon(QIcon(imageButtonFile))
        imageButton.clicked.connect(self.openImageDialog)
        self.toolBar.addWidget(imageButton)

        self.toolBar.addSeparator()

    def setupToolBarFullIconSize(self):

        self.toolBar = QToolBar()
        self.toolBar.setWindowTitle("Tool Bar")
        self.toolBar.setContextMenuPolicy(Qt.PreventContextMenu)
        # self.toolBar can be treated as an individual widget and positioned with a specified layout
        # In QMainWindow, the following line adds the configured QToolBar as part of the toolbar of the main window
        self.addToolBar(self.toolBar)

        iconFile = os.path.join("htmlResources", "bold.png")
        self.toolBar.addAction(QIcon(iconFile), "Bold \n[Shortcut: Ctrl/Cmd + B]", self.format_bold)

        iconFile = os.path.join("htmlResources", "italic.png")
        self.toolBar.addAction(QIcon(iconFile), "Italic \n[Shortcut: Ctrl/Cmd + I]", self.format_italic)

        iconFile = os.path.join("htmlResources", "underline.png")
        self.toolBar.addAction(QIcon(iconFile), "Underline \n[Shortcut: Ctrl/Cmd + U]", self.format_underline)

        self.toolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "custom.png")
        self.toolBar.addAction(QIcon(iconFile), "Transform Selected Text: \n[Shortcut: Ctrl/Cmd + M] \n \nBullet List, e.g.: \n* bullet one \n* bullet two \n \nNumbered List, e.g.: \n*1 numbered item one \n*2 numbered item two \n \nTable, e.g.: \n{one|two|three} \n{four|five|six}", self.format_custom)

        self.toolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "align_left.png")
        self.toolBar.addAction(QIcon(iconFile), "Align Left", self.format_left)

        iconFile = os.path.join("htmlResources", "align_center.png")
        self.toolBar.addAction(QIcon(iconFile), "Center Text", self.format_center)

        iconFile = os.path.join("htmlResources", "align_right.png")
        self.toolBar.addAction(QIcon(iconFile), "Align Right", self.format_right)

        iconFile = os.path.join("htmlResources", "align_justify.png")
        self.toolBar.addAction(QIcon(iconFile), "Justify", self.format_justify)

        self.toolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "clearFormat.png")
        self.toolBar.addAction(QIcon(iconFile), "Delete Formatting \n[Shortcut: Ctrl/Cmd + D]", self.format_clear)

        self.toolBar.addSeparator()

        iconFile = os.path.join("htmlResources", "hyperlink.png")
        self.toolBar.addAction(QIcon(iconFile), "Add a Hyperlink", self.openHyperlinkDialog)

        iconFile = os.path.join("htmlResources", "gallery.png")
        self.toolBar.addAction(QIcon(iconFile), "Add an Image", self.openImageDialog)

        self.toolBar.addSeparator()

    def setupLayout(self):
        self.editor = QTextEdit()
        self.editor.textChanged.connect(self.textChanged)
        self.setCentralWidget(self.editor)

        #self.layout = QGridLayout()
        #self.layout.setMenuBar(self.menuBar)
        #self.layout.addWidget(self.toolBar, 0, 0)
        #self.layout.addWidget(self.editor, 1, 0)
        #self.setLayout(self.layout)

    # adjustment of note editor font size
    def increaseNoteEditorFontSize(self):
        if self.html:
            self.editor.selectAll()
            config.noteEditorFontSize += 1
            self.editor.setFontPointSize(config.noteEditorFontSize)
            self.hide()
            self.show()

    def decreaseNoteEditorFontSize(self):
        if self.html and not config.noteEditorFontSize == 0:
            self.editor.selectAll()
            config.noteEditorFontSize -= 1
            self.editor.setFontPointSize(config.noteEditorFontSize)
            self.hide()
            self.show()

    # search field entered
    def searchLineEntered(self):
        searchString = self.searchLineEdit.text()
        if searchString:
            cursor = self.editor.document().find(searchString, self.editor.textCursor())
        if cursor:
            self.editor.setTextCursor(cursor)
        self.hide()
        self.show()

    def focusSearchField(self):
        self.searchLineEdit.setFocus()

    # track if the text being modified
    def textChanged(self):
        if self.parent.noteSaved:
            self.parent.noteSaved = False
            self.updateWindowTitle()

    # display content when first launched
    def displayInitialContent(self):
        if self.noteType == "file":
            if self.noteFileName:
                self.openNoteFile(self.noteFileName)
            else:
                self.newNoteFile()
        else:
            self.b, self.c, self.v = config.studyB, config.studyC, config.studyV
            self.openBibleNote()

        self.editor.selectAll()
        self.editor.setFontPointSize(config.noteEditorFontSize)
        self.editor.moveCursor(QTextCursor.Start, QTextCursor.MoveAnchor)

        self.parent.noteSaved = True

    # load chapter / verse notes from sqlite database
    def openBibleNote(self):
        noteSqlite = NoteSqlite()
        if self.noteType == "chapter":
            note = noteSqlite.getChapterNote((self.b, self.c))
        elif self.noteType == "verse":
            note = noteSqlite.getVerseNote((self.b, self.c, self.v))
        del noteSqlite
        #self.editor.setPlainText(note)
        self.editor.setHtml(note)

    # File I / O
    def newNoteFile(self):
        if self.parent.noteSaved:
            self.newNoteFileAction()
        elif self.parent.warningNotSaved():
            self.newNoteFileAction()

    def newNoteFileAction(self):
        self.noteType = "file"
        self.noteFileName = ""
        self.editor.clear()
        self.parent.noteSaved = True
        self.updateWindowTitle()
        self.hide()
        self.show()

    def openFileDialog(self):
        if self.parent.noteSaved:
            self.openFileDialogAction()
        elif self.parent.warningNotSaved():
            self.openFileDialogAction()

    def openFileDialogAction(self):
        options = QFileDialog.Options()
        fileName, filtr = QFileDialog.getOpenFileName(self,
                "QFileDialog.getOpenFileName()",
                self.parent.openFileNameLabel.text(),
                "UniqueBible.app Note Files (*.uba);;HTML Files (*.html);;HTM Files (*.htm);;All Files (*)", "", options)
        if fileName:
            self.openNoteFile(fileName)

    def openNoteFile(self, fileName):
        try:
            f = open(fileName,'r')
        except:
            print("Failed to open '{0}'".format(fileName))
        note = f.read()
        f.close()
        self.noteType = "file"
        self.noteFileName = fileName
        if self.html:
            self.editor.setHtml(note)
        else:
            self.editor.setPlainText(note)
        self.parent.noteSaved = True
        self.updateWindowTitle()
        self.hide()
        self.show()

    def saveNote(self):
        if self.html:
            note = self.editor.toHtml()
        else:
            note = self.editor.toPlainText()
        if self.noteType == "chapter":
            noteSqlite = NoteSqlite()
            noteSqlite.saveChapterNote((self.b, self.c, note))
            del noteSqlite
            self.parent.openChapterNote(self.b, self.c)
            self.parent.noteSaved = True
            self.updateWindowTitle()
        elif self.noteType == "verse":
            noteSqlite = NoteSqlite()
            noteSqlite.saveVerseNote((self.b, self.c, self.v, note))
            del noteSqlite
            self.parent.openVerseNote(self.b, self.c, self.v)
            self.parent.noteSaved = True
            self.updateWindowTitle()
        elif self.noteType == "file":
            if self.noteFileName == "":
                self.openSaveAsDialog()
            else:
                self.saveAsNote(self.noteFileName)

    def openSaveAsDialog(self):
        if self.noteFileName:
            *_, defaultName = os.path.split(self.noteFileName)
        else:
            defaultName = "new.uba"
        options = QFileDialog.Options()
        fileName, filtr = QFileDialog.getSaveFileName(self,
                "QFileDialog.getSaveFileName()",
                defaultName,
                "UniqueBible.app Note Files (*.uba);;HTML Files (*.html);;HTM Files (*.htm);;All Files (*)", "", options)
        if fileName:
            self.saveAsNote(fileName)

    def saveAsNote(self, fileName):
        if self.html:
            note = self.editor.toHtml()
        else:
            note = self.editor.toPlainText()
        f = open(fileName,'w')
        f.write(note)
        f.close()
        self.noteFileName = fileName
        self.parent.addExternalFileHistory(fileName)
        self.parent.setExternalFileButton()
        self.parent.noteSaved = True
        self.updateWindowTitle()

    # formatting styles
    def format_clear(self):
        selectedText = self.editor.textCursor().selectedText()
        if self.html:
            self.editor.insertHtml(selectedText)
        else:
            selectedText = re.sub("<[^\n<>]*?>", "", selectedText)
            self.editor.insertPlainText(selectedText)
        self.hide()
        self.show()

    def format_bold(self):
        if self.html:
            self.editor.setFontWeight(75)
        else:
            self.editor.insertPlainText("<b>{0}</b>".format(self.editor.textCursor().selectedText()))
        self.hide()
        self.show()

    def format_italic(self):
        if self.html:
            self.editor.setFontItalic(True)
        else:
            self.editor.insertPlainText("<i>{0}</i>".format(self.editor.textCursor().selectedText()))
        self.hide()
        self.show()

    def format_underline(self):
        if self.html:
            self.editor.setFontUnderline(True)
        else:
            self.editor.insertPlainText("<u>{0}</u>".format(self.editor.textCursor().selectedText()))
        self.hide()
        self.show()

    def format_center(self):
        if self.html:
            self.editor.setAlignment(Qt.AlignCenter)
        else:
            self.editor.insertPlainText("<div style='text-align:center;'>{0}</div>".format(self.editor.textCursor().selectedText()))
        self.hide()
        self.show()

    def format_justify(self):
        if self.html:
            self.editor.setAlignment(Qt.AlignJustify)
        else:
            self.editor.insertPlainText("<div style='text-align:justify;'>{0}</div>".format(self.editor.textCursor().selectedText()))
        self.hide()
        self.show()

    def format_left(self):
        if self.html:
            self.editor.setAlignment(Qt.AlignLeft)
        else:
            self.editor.insertPlainText("<div style='text-align:left;'>{0}</div>".format(self.editor.textCursor().selectedText()))
        self.hide()
        self.show()

    def format_right(self):
        if self.html:
            self.editor.setAlignment(Qt.AlignRight)
        else:
            self.editor.insertPlainText("<div style='text-align:right;'>{0}</div>".format(self.editor.textCursor().selectedText()))
        self.hide()
        self.show()

    def format_custom(self):
        selectedText = self.editor.textCursor().selectedText()
        selectedText = self.customFormat(selectedText)
        if self.html:
            self.editor.insertHtml(selectedText)
        else:
            self.editor.insertPlainText(selectedText)
        self.hide()
        self.show()

    def customFormat(self, text):
        # QTextEdit's line break character by pressing ENTER in plain & html mode " "
        # please note that " " is not an empty string
        text = text.replace(" ", "\n")

        text = re.sub("^\*[0-9]+? (.*?)$", r"<ol><li>\1</li></ol>", text, flags=re.M)
        text = text.replace("</ol>\n<ol>", "\n")
        text = re.sub("^\* (.*?)$", r"<ul><li>\1</li></ul>", text, flags=re.M)
        text = text.replace("</ul>\n<ul>", "\n")
        text = re.sub("^{.*?}$", self.formatHTMLTable, text, flags=re.M)
        text = text.replace("</table>\n<table>", "\n")

        # add style to table here
        # please note that QTextEdit supports HTML 4, rather than HTML 5
        # take this old reference: https://www.w3schools.com/tags/tag_table.asp
        text = text.replace('<table>', '<table border="1" cellpadding="5">')

        # convert back to QTextEdit linebreak
        text = text.replace("\n", " ")

        return text

    def formatHTMLTable(self, match):
        row = match.group()[1:-1]
        row = "".join(["<td>{0}</td>".format(cell) for cell in row.split("|")])
        return "<table><tr>{0}</tr></table>".format(row)

    def addImage(self, fileName):
        imageTag = '<img src="{0}" alt="UniqueBible.app">'.format(fileName)
        if self.html:
            self.editor.insertHtml(imageTag)
        else:
            self.editor.insertPlainText(imageTag)
        self.hide()
        self.show()

    def openImageDialog(self):
        options = QFileDialog.Options()
        fileName, filtr = QFileDialog.getOpenFileName(self,
                "QFileDialog.getOpenFileName()",
                self.parent.openFileNameLabel.text(),
                "JPG Files (*.jpg);;JPEG Files (*.jpeg);;PNG Files (*.png);;GIF Files (*.gif);;BMP Files (*.bmp);;All Files (*)", "", options)
        if fileName:
            self.addImage(fileName)

    def addHyperlink(self, hyperlink):
        hyperlink = '<a href="{0}">{0}</a>'.format(hyperlink)
        if self.html:
            self.editor.insertHtml(hyperlink)
        else:
            self.editor.insertPlainText(hyperlink)
        self.hide()
        self.show()

    def openHyperlinkDialog(self):
        selectedText = self.editor.textCursor().selectedText()
        if selectedText:
            hyperlink = selectedText
        else:
            hyperlink = "https://BibleTools.app"
        text, ok = QInputDialog.getText(self, "Add a hyperlink ...",
                "Hyperlink:", QLineEdit.Normal,
                hyperlink)
        if ok and text != '':
            self.addHyperlink(text)


class ImportSettings(QDialog):

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setModal(True)

        self.setWindowTitle("Import settings")

        self.setupLayout()

    def setupLayout(self):
        titleBibles = QLabel("Bibles:")

        self.linebreak = QCheckBox()
        self.linebreak.setText("Additional linebreak for each verse")
        self.linebreak.setChecked(config.importAddVerseLinebreak)

        self.stripStrNo = QCheckBox()
        self.stripStrNo.setText("Keep Strong's numbers for search")
        self.stripStrNo.setChecked(config.importDoNotStripStrongNo)

        self.stripMorphCode = QCheckBox()
        self.stripMorphCode.setText("Keep morphology codes for search")
        self.stripMorphCode.setChecked(config.importDoNotStripMorphCode)

        self.importRtlOT = QCheckBox()
        self.importRtlOT.setText("Right-to-Left display for Old Testament")
        self.importRtlOT.setChecked(config.importRtlOT)

        saveButton = QPushButton("Save")
        saveButton.clicked.connect(self.saveSettings)

        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)

        self.layout = QGridLayout()
        self.layout.addWidget(titleBibles, 0, 0)
        self.layout.addWidget(self.linebreak, 1, 0)
        self.layout.addWidget(self.stripStrNo, 2, 0)
        self.layout.addWidget(self.stripMorphCode, 3, 0)
        self.layout.addWidget(self.importRtlOT, 4, 0)
        self.layout.addWidget(saveButton, 5, 0)
        self.layout.addWidget(cancelButton, 6, 0)
        self.setLayout(self.layout)

    def saveSettings(self):
        if self.linebreak.isChecked():
            config.importAddVerseLinebreak = True
        else:
            config.importAddVerseLinebreak = False

        if self.stripStrNo.isChecked():
            config.importDoNotStripStrongNo = True
        else:
            config.importDoNotStripStrongNo = False

        if self.stripMorphCode.isChecked():
            config.importDoNotStripMorphCode = True
        else:
            config.importDoNotStripMorphCode = False

        if self.importRtlOT.isChecked():
            config.importRtlOT = True
        else:
            config.importRtlOT = False

        self.close()


class Downloader(QDialog):

    def __init__(self, parent, databaseInfo):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Download Helper")
        self.setModal(True)

        fileItems, cloudID = databaseInfo
        self.cloudFile = "https://drive.google.com/uc?id={0}".format(cloudID)
        self.localFile = "{0}.zip".format(os.path.join(*fileItems))
        self.filename = fileItems[-1]

        self.setupLayout()

    def setupLayout(self):

        #self.setupProgressBar()

        message = QLabel("File '{0}' is required for running the feature you selected.".format(self.filename))

        downloadButton = QPushButton("Download + Install")
        downloadButton.clicked.connect(self.startDownloadFile)

        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)

        remarks = QLabel("Remarks: It takes time for large files to be downloaded.")

        self.layout = QGridLayout()
        #self.layout.addWidget(self.progressBar, 0, 0)
        self.layout.addWidget(message, 0, 0)
        self.layout.addWidget(downloadButton, 1, 0)
        self.layout.addWidget(cancelButton, 2, 0)
        self.layout.addWidget(remarks, 3, 0)
        self.setLayout(self.layout)

    def setupProgressBar(self):
        self.progressBar = QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)

    def startDownloadFile(self):
        self.downloadFile(True)

    def downloadFile(self, interactWithParent=True):
        try:
            #gdown.download(self.cloudFile, self.localFile, quiet=True)
            connection = True
        except:
            connection = False
        if connection:
            if self.localFile.endswith(".zip"):
                zip = zipfile.ZipFile(self.localFile, "r")
                path, *_ = os.path.split(self.localFile)
                zip.extractall(path)
                zip.close()
                os.remove(self.localFile)
            if interactWithParent:
                self.parent.moduleInstalled(self.filename)
        else:
            if interactWithParent:
                self.parent.moduleInstalledFailed(self.filename)
