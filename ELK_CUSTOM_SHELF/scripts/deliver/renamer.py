# ELK_META {"label": "Renamer Tool", "short_name": "Rename", "tooltip": "Outil avancé de renommage d’objets.", "source": "python", "icon_svg": "edit.svg", "icon_color": "#f2c94c"}
#
# Copyright (C) by Adrian Sochacki, since 2019. All rights reserved.
#
# Description: Gives you the function to easily rename everything
#
# How to use: Run the script, change the textfields depending on the rename method and hit the corresponding button.
#
# Version: 1.2.1
#

import maya.cmds as cmds
import sys
from functools import partial


def onMayaDroppedPythonFile(*args):
	RenameWindow()


def RenameWindow(*args):
	winID = 'schocki_renameWindowUI'
	if cmds.window(winID, exists = True):
		cmds.deleteUI(winID)

	if cmds.windowPref(winID, exists = True):
		topLeftCorner = cmds.windowPref(winID, query = True, topLeftCorner = True)
		cmds.windowPref(winID, remove = True)
	else:
		topLeftCorner = (197, 442)

	itemWidth = 278

	cmds.window(winID, title = 'Renamer',width = 294, sizeable = False, topLeftCorner = topLeftCorner, minimizeCommand = SaveOptionVariables, closeCommand = SaveOptionVariables)
	cmds.columnLayout('masterRowLayout')
	cmds.separator(style = 'none', height = 5)

	#Add string at position
	addStringAtPositionAnnotation = 'Add a string at a specific position:\nChange "Cube1" to "masterCube1"\nChange "Cube1" to "Cube1_master"\nChange "Cube1" to "Cu_master_be1"'

	cmds.rowColumnLayout('addStringAtPositionRowColumnLayout', numberOfColumns = 3, annotation = addStringAtPositionAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text('Add string at position :', font = 'boldLabelFont')
	cmds.separator(style = 'none', width = 5)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout1', annotation = addStringAtPositionAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns = 4, annotation = addStringAtPositionAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'String to add :')
	cmds.separator(style = 'none', width = 5)
	cmds.textField('stringToAddTextField', width = 199)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout2', annotation = addStringAtPositionAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns = 4, annotation = addStringAtPositionAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'At position :')
	cmds.separator(style = 'none', width = 5)
	cmds.intField('stringToAddAtPositionIntField', width = 210, minValue = 0)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout3', annotation = addStringAtPositionAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#Button
	cmds.rowColumnLayout(numberOfColumns = 2, annotation = addStringAtPositionAnnotation)
	cmds.separator(style = 'none', width = 5)
	cmds.button('addStringAtPositionButton', label = 'Add string at position', width = itemWidth+1, command = partial(PreRename, 'addStringAtPosition'))
	cmds.setParent('..')

	#Separator
	cmds.rowColumnLayout('separatorRowColumnLayout1', numberOfColumns = 3)
	cmds.separator(style = 'none', width = 5)
	cmds.separator(height = 10, width = itemWidth)
	cmds.separator(style = 'none', width = 3)
	cmds.setParent('..')

	#Replace string
	replaceStringAnnotation = 'Replace a string with another one:\nChange "pCube1" to "pSphere1"\nChange "testCurve" to "masterCurve"'

	cmds.rowColumnLayout('replaceStringRowColumnLayout', numberOfColumns = 3, annotation = replaceStringAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text('Replace string with string :', font = 'boldLabelFont')
	cmds.separator(style = 'none', width = 5)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout5', annotation = replaceStringAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#TextField
	cmds.rowColumnLayout(numberOfColumns = 4, annotation = replaceStringAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'Replace string :')
	cmds.separator(style = 'none', width = 5)
	cmds.textField('toReplaceTextField', width = 194)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout6', annotation = replaceStringAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#TextField
	cmds.rowColumnLayout(numberOfColumns = 4, annotation = replaceStringAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'With string :')
	cmds.separator(style = 'none', width = 5)
	cmds.textField('replaceWithTextField', width = 209)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout7', annotation = replaceStringAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#Button
	cmds.rowColumnLayout(numberOfColumns = 2, annotation = replaceStringAnnotation)
	cmds.separator(style = 'none', width = 5)
	cmds.button('replaceStringButton', label = 'Replace string with string', width = itemWidth+1, command = partial(PreRename, 'replaceWith'))
	cmds.setParent('..')

	#Separator
	cmds.rowColumnLayout('separatorRowColumnLayout3', numberOfColumns = 3)
	cmds.separator(style = 'none', width = 5)
	cmds.separator(height = 10, width = itemWidth)
	cmds.separator(style = 'none', width = 3)
	cmds.setParent('..')

	#Add padding
	addPaddingAnnotation = 'Adds a padding that goes up for every object you have selected:\nChanges your first selected object from "pCube" to "pCube0100"\nChanges your second selected object from "pSphere" to "pSphere0101"\nChanges your third selected object from "pCone" to "pCone0102"'

	cmds.rowColumnLayout('addPaddingRowColumnLayout', numberOfColumns = 3, annotation = addPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text('Add padding :', font = 'boldLabelFont')
	cmds.separator(style = 'none', width = 5)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout10', annotation = addPaddingAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#IntField
	cmds.rowColumnLayout(numberOfColumns = 4, annotation = addPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'How much padding :')
	cmds.separator(style = 'none', width = 5)
	cmds.intField('paddingCountIntField', width = 165, minValue = 0)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout11', annotation = addPaddingAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#IntField
	cmds.rowColumnLayout(numberOfColumns = 4, annotation = addPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'Start at(integer) :')
	cmds.separator(style = 'none', width = 5)
	cmds.intField('startAtIntField', width = 187, minValue = 0)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout12', annotation = addPaddingAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#IntField
	cmds.rowColumnLayout(numberOfColumns = 4, annotation = addPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'Add at following position :')
	cmds.separator(style = 'none', width = 5)
	cmds.intField('addAtFollowingIntField', width = 134, minValue = 0)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout13', annotation = addPaddingAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#Button
	cmds.rowColumnLayout(numberOfColumns = 2, annotation = addPaddingAnnotation)
	cmds.separator(style = 'none', width = 5)
	cmds.button('addPaddingButton', label = 'Add padding', width = itemWidth+1, command = partial(PreRename, 'addPadding'))
	cmds.setParent('..')

	#Separator
	cmds.rowColumnLayout('separatorRowColumnLayout4', numberOfColumns = 3)
	cmds.separator(style = 'none', width = 5)
	cmds.separator(height = 10, width = itemWidth)
	cmds.separator(style = 'none', width = 3)
	cmds.setParent('..')

	#Rename and add padding
	renameAndAddPaddingAnnotation = 'Renames and adds a padding that goes up for every object you have selected\nChanges first selected object, "pCube1" to "pCube_001"\nChanges second selected object, "pSphere" to "pCube_002"\nChanges first selected object, "pTorus" to "pCube_003"\nFormula: renameTo + specialCharacter + paddingAmount'

	cmds.rowColumnLayout('renameAndAddPaddingRowColumnLayout', numberOfColumns = 3, annotation = addPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text('Rename and add padding :', font = 'boldLabelFont')
	cmds.separator(style = 'none', width = 5)
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns = 4, annotation = renameAndAddPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'How much padding :')
	cmds.separator(style = 'none', width = 5)
	cmds.intField('renameAndAddPaddingCountIntField', width = 165, minValue = 0)
	cmds.setParent('..')

	#IntField
	cmds.rowColumnLayout(numberOfColumns = 4, annotation = renameAndAddPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'Start at(integer) :')
	cmds.separator(style = 'none', width = 5)
	cmds.intField('renameAndAddPaddingStartAtIntField', width = 187, minValue = 0)
	cmds.setParent('..')

	#Text Field
	cmds.rowColumnLayout(numberOfColumns = 4, annotation = renameAndAddPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'Special character separator :')
	cmds.separator(style = 'none', width = 5)
	cmds.textField('renameAndAddPaddingSpecialCharacterSeparatorTextField', width = 129)
	cmds.setParent('..')

	#Text Field
	cmds.rowColumnLayout(numberOfColumns = 4, annotation = renameAndAddPaddingAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text(label = 'Rename to :')
	cmds.separator(style = 'none', width = 5)
	cmds.textField('renameAndAddPaddingRenameToTextField', width = 212)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout19', annotation = addPaddingAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	#Button
	cmds.rowColumnLayout(numberOfColumns = 2, annotation = addPaddingAnnotation)
	cmds.separator(style = 'none', width = 5)
	cmds.button('renameAndAddPaddingButton', label = 'Rename and add padding', width = itemWidth+1, command = partial(PreRename, 'renameAndAddPadding'))
	cmds.setParent('..')

	#Separator
	cmds.rowColumnLayout('separatorRowColumnLayout10', numberOfColumns = 3)
	cmds.separator(style = 'none', width = 5)
	cmds.separator(height = 10, width = itemWidth)
	cmds.separator(style = 'none', width = 3)
	cmds.setParent('..')

	#Quick prefix/suffix
	quickPrefixSuffixAnnotation = 'Quickly adds text as a prefix or suffix to your selection:\nChanges "pCube" to "pCubeGEO\nChanges "NurbsCurve" to "crvNurbsCurve"'

	cmds.rowColumnLayout('quickPrefixSuffixRowColumnLayout', numberOfColumns = 3, annotation = quickPrefixSuffixAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text('Add prefix/suffix :', font = 'boldLabelFont')
	cmds.separator(style = 'none', width = 5)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout14', annotation = quickPrefixSuffixAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	cmds.rowLayout(numberOfColumns = 4, annotation = quickPrefixSuffixAnnotation)
	cmds.separator(style = 'none', width = 6)
	cmds.radioCollection()
	cmds.radioButton('prefixRadioButton', label = 'Prefix')
	cmds.separator(style = 'none', width = 41)
	cmds.radioButton('suffixRadioButton', label = 'Suffix')
	cmds.setParent('..')
	cmds.rowLayout(numberOfColumns = 4)
	cmds.separator(style = 'none', width = 6)
	cmds.radioCollection()
	cmds.radioButton('lowercaseRadioButton', label = 'Lowercase', onCommand = partial(ChangeButtonLabel, 'lowercase'))
	cmds.separator(style = 'none', width = 15)
	cmds.radioButton('uppercaseRadioButton', label = 'Uppercase', onCommand = partial(ChangeButtonLabel, 'uppercase'))
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout15', annotation = quickPrefixSuffixAnnotation)
	cmds.separator(height = 3)
	cmds.setParent('..')

	cmds.rowLayout('buttonRowLayout1', numberOfColumns = 7, annotation = quickPrefixSuffixAnnotation)
	cmds.separator(style = 'none', width = 6)
	cmds.button('geoButton', label = 'geo', command = partial(PreRename, 'quickPrefixSuffix', 'geo'), width = 44)
	cmds.button('grpButton', label = 'grp', command = partial(PreRename, 'quickPrefixSuffix', 'grp'), width = 44)
	cmds.button('animButton', label = 'anim', command = partial(PreRename, 'quickPrefixSuffix', 'anim'), width = 44)
	cmds.button('locButton', label = 'loc', command = partial(PreRename, 'quickPrefixSuffix', 'loc'), width = 44)
	cmds.button('camButton', label = 'cam', command = partial(PreRename, 'quickPrefixSuffix', 'cam'), width = 44)
	cmds.button('jntButton', label = 'jnt', command = partial(PreRename, 'quickPrefixSuffix', 'jnt'), width = 44)
	cmds.setParent('..')
	cmds.rowLayout('buttonRowLayout2', numberOfColumns = 7, annotation = quickPrefixSuffixAnnotation)
	cmds.separator(style = 'none', width = 6)
	cmds.button('proxyButton', label = 'proxy', command = partial(PreRename, 'quickPrefixSuffix', 'proxy'), width = 44)
	cmds.button('lgtButton', label = 'lgt', command = partial(PreRename, 'quickPrefixSuffix', 'lgt'), width = 44)
	cmds.button('crvButton', label = 'crv', command = partial(PreRename, 'quickPrefixSuffix', 'crv'), width = 44)
	cmds.button('ikButton', label = 'ik', command = partial(PreRename, 'quickPrefixSuffix', 'ik'), width = 44)
	cmds.button('fkButton', label = 'fk', command = partial(PreRename, 'quickPrefixSuffix', 'fk'), width = 44)
	cmds.button('setButton', label = 'set', command = partial(PreRename, 'quickPrefixSuffix', 'set'), width = 44)
	cmds.setParent('..')
	cmds.rowLayout('buttonRowLayout3', numberOfColumns = 7, annotation = quickPrefixSuffixAnnotation)
	cmds.separator(style = 'none', width = 6)
	cmds.button('nrbButton', label = 'nrb', command = partial(PreRename, 'quickPrefixSuffix', 'nrb'), width = 44)
	cmds.button('dummyButton', label = 'dummy', command = partial(PreRename, 'quickPrefixSuffix', 'dummy'), width = 44)
	cmds.button('clustButton', label = 'clust', command = partial(PreRename, 'quickPrefixSuffix', 'clust'), width = 44)
	cmds.button('infButton', label = 'inf', command = partial(PreRename, 'quickPrefixSuffix', 'inf'), width = 44)
	cmds.button('constButton', label = 'const', command = partial(PreRename, 'quickPrefixSuffix', 'const'), width = 44)
	cmds.button('fxButton', label = 'fx', command = partial(PreRename, 'quickPrefixSuffix', 'fx'), width = 44)
	cmds.setParent('..')

	#Separator
	cmds.rowColumnLayout('separatorRowColumnLayout5', numberOfColumns = 3)
	cmds.separator(style = 'none', width = 5)
	cmds.separator(height = 10, width = itemWidth)
	cmds.separator(style = 'none', width = 3)
	cmds.setParent('..')

	#Remove character
	removeCharacterAnnotation = 'Removes first or last character:\nChanges "pCube1" to "Cube1"\nChanges "pSphere1" to "pSphere"'

	cmds.rowColumnLayout('removeRowColumnLayout', numberOfColumns = 3, annotation = removeCharacterAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text('Remove character :', font = 'boldLabelFont')
	cmds.separator(style = 'none', width = 5)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout16', annotation = removeCharacterAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	cmds.rowLayout(numberOfColumns = 3, annotation = removeCharacterAnnotation)
	cmds.separator(style = 'none', width = 5)
	cmds.button('removeFirstButton', label = 'Remove first character', width = 137, command = partial(PreRename, 'removeCharacter', 'first'))
	cmds.button('removeLastButton', label = 'Remove last character', width = 137, command = partial(PreRename, 'removeCharacter', 'last'))
	cmds.setParent('..')

	#Separator
	cmds.rowColumnLayout('separatorRowColumnLayout7', numberOfColumns = 3)
	cmds.separator(style = 'none', width = 5)
	cmds.separator(height = 10, width = itemWidth)
	cmds.separator(style = 'none', width = 3)
	cmds.setParent('..')

	#Rename shape
	renameShapeAnnotation = "Renames the shape corresponding to it's transform name. Fixes some errors that depend on correct shape names"

	cmds.rowColumnLayout('renameShapeRowColumnLayout', numberOfColumns = 3, annotation = renameShapeAnnotation)
	cmds.separator(style = 'none', width = 7)
	cmds.text('Rename shape :', font = 'boldLabelFont')
	cmds.separator(style = 'none', width = 5)
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout17', annotation = renameShapeAnnotation)
	cmds.separator(height = 1)
	cmds.setParent('..')

	cmds.rowLayout(numberOfColumns = 2, annotation = renameShapeAnnotation)
	cmds.separator(style = 'none', width = 5)
	cmds.button('renameShapeButton', label = 'Rename shapes', width = itemWidth-2, command = partial(PreRename, 'renameShape'))
	cmds.setParent('..')

	#Space
	cmds.rowLayout('spaceRowLayout18', annotation = renameShapeAnnotation)
	cmds.separator(height = 4)
	cmds.setParent('..')

	cmds.setParent('..')

	if not cmds.radioButton('prefixRadioButton', query = True, select = True) and not cmds.radioButton('suffixRadioButton', query = True, select = True):
		cmds.radioButton('prefixRadioButton', edit = True, select = True)
		cmds.radioButton('suffixRadioButton', edit = True, select = False)

	if not cmds.radioButton('lowercaseRadioButton', query = True, select = True) and not cmds.radioButton('uppercaseRadioButton', query = True, select = True):
		cmds.radioButton('lowercaseRadioButton', edit = True, select = True)
		cmds.radioButton('uppercaseRadioButton', edit = True, select = False)

	CheckOptionVariables()

	cmds.showWindow()


def PreRename(command, extra, *args):
	sel = cmds.ls(sl = True)
	if len(sel) == 0:
		sys.exit('You have nothing selected. Please select at least one object.\n')
	else:
		cmds.undoInfo(chunkName = 'batchRenamer_rename', openChunk = True)
		if command == 'addStringAtPosition':
			AddStringAtPosition(sel)

		elif command == 'replaceWith':
			ReplaceWith(sel)

		elif command == 'addPadding':
			AddPadding(sel)

		elif command == 'quickPrefixSuffix':
			QuickPrefixSuffix(sel, extra)

		elif command == 'removeCharacter':
			if extra == 'first':
				RemoveCharacter(sel, extra)
			elif extra == 'last':
				RemoveCharacter(sel, extra)

		elif command == 'renameShape':
			RenameShape(sel)

		elif command == 'renameAndAddPadding':
			RenameAndAddPadding(sel)
		else:
			sys.exit('Unexpected Error, Please contact me.')
			cmds.undoInfo(chunkName = 'batchRenamer_rename', closeChunk = True)
		cmds.undoInfo(chunkName = 'batchRenamer_rename', closeChunk = True)

	SaveOptionVariables()


def AddStringAtPosition(sel, *args):
	stringToAdd = cmds.textField('stringToAddTextField', query = True, text = True)

	if stringToAdd == '':
		sys.exit('The "String to add" text field is empty, please type something in.\n')
	addAtPos = cmds.intField('stringToAddAtPositionIntField', query = True, value = True)

	if addAtPos == 0 or addAtPos == 1:
		addAtPos = 0
	else:
		addAtPos -= 1

	for x in sel:
		cmds.rename(x, x[:addAtPos] + stringToAdd + x[addAtPos:])
		sys.stdout.write('Renamed "' + x + '" to "' + x[:addAtPos] + stringToAdd + x[addAtPos:] + '".\n')


def ReplaceWith(sel, *args):
	toReplace = cmds.textField('toReplaceTextField', query = True, text = True)
	replaceWith = cmds.textField('replaceWithTextField', query = True, text = True)
	if toReplace == '' and replaceWith == '':
		sys.exit('The "Replace string" text field is empty, please type something in.\n')
	elif toReplace == '':
		sys.exit('The "Replace string" and "With string" textfields are empty, please type something in.\n')

	for x in sel:
		cmds.rename(x, x.replace(str(toReplace), str(replaceWith)))
		sys.stdout.write('Replaced "' + toReplace + '" with "' + replaceWith + '".\n')


def AddPadding(sel, *args):
	paddingNumber = cmds.intField('paddingCountIntField', query = True, value = True)
	startAt = cmds.intField('startAtIntField', query = True, value = True)
	addAtPos = cmds.intField('addAtFollowingIntField', query = True, value = True)

	if paddingNumber == '':
		sys.exit('The "How much padding" text field is empty, please type something in.\n')
	elif startAt == '':
		sys.exit('The "Start at" text field is empty, please type something in.\n')
	elif addAtPos == '':
		sys.exit('The "Add at following position" text field is empty, please type something in.\n')

	if addAtPos == 0 or addAtPos == 1:
		addAtPos = 0
	else:
		addAtPos -= 1

	for x in range(len(sel)):
		if addAtPos > len(sel[x]):
			cmds.rename(sel[x], sel[x] + str(startAt).zfill(paddingNumber))
		elif addAtPos > 0:
			cmds.rename(sel[x], sel[x][:addAtPos] + str(startAt).zfill(paddingNumber) + sel[x][addAtPos:])
		elif addAtPos == 0:
			cmds.rename(sel[x], str(startAt).zfill(paddingNumber) + sel[x])
		else:
			cmds.rename(sel[x], sel[x] + str(x + 1).zfill(paddingNumber - len(str(x))))
		sys.stdout.write('Added padding to ' + sel[x] + '.\n')
		startAt += 1


def RenameAndAddPadding(sel, *args):
	paddingNumber = cmds.intField('renameAndAddPaddingCountIntField', query = True, value = True)
	startAt = cmds.intField('renameAndAddPaddingStartAtIntField', query = True, value = True)
	specialCharacter = cmds.textField('renameAndAddPaddingSpecialCharacterSeparatorTextField', query = True, text = True)
	renameTo = cmds.textField('renameAndAddPaddingRenameToTextField', query = True, text = True)

	if paddingNumber == '':
		sys.exit('The "How much padding" text field is empty, please type something in.\n')
	if startAt == '':
		sys.exit('The "Start at" text field is empty, please type something in.\n')
	if renameTo == '':
		sys.exit('The "Rename to" text field is empty, please type something in.asd\n')

	for x in range(len(sel)):
		newName = renameTo + specialCharacter + str(startAt + x).zfill(paddingNumber)
		cmds.rename(sel[x], newName)
		sys.stdout.write('Renamed ' + sel[x] + ' to ' + newName + '.\n')


def QuickPrefixSuffix(sel, toAddFix, *args):
	lowercase = cmds.radioButton('lowercaseRadioButton', query = True, select = True)
	uppercase = cmds.radioButton('uppercaseRadioButton', query = True, select = True)

	prefix = cmds.radioButton('prefixRadioButton', query = True, select = True)
	suffix = cmds.radioButton('suffixRadioButton', query = True, select = True)
	for x in sel:
		if prefix and not suffix:
			if lowercase and not uppercase:
				cmds.rename(toAddFix.lower() + x)
				sys.stdout.write('Renamed "' + x + '" to "' + toAddFix.lower() + x + '".\n')
			elif not lowercase and uppercase:
				cmds.rename(toAddFix.upper() + x)
				sys.stdout.write('Renamed "' + x + '" to "' + toAddFix.upper() + x + '".\n')

		elif not prefix and suffix:
			if lowercase and not uppercase:
				cmds.rename(x + toAddFix.lower())
				sys.stdout.write('Renamed "' + x + '" to "' + x + toAddFix.lower() + '".\n')
			elif not lowercase and uppercase:
				cmds.rename(x + toAddFix.upper())
				sys.stdout.write('Renamed "' + x + '" to "' + x + toAddFix.upper() + '".\n')
		else:
			sys.exit('Unexpected Error, please contact me.\n')


def ChangeButtonLabel(case, *args):
	if case == 'lowercase':
		cmds.button('geoButton', edit = True, label = 'geo')
		cmds.button('grpButton', edit = True, label = 'grp')
		cmds.button('animButton', edit = True, label = 'anim')
		cmds.button('locButton', edit = True, label = 'loc')
		cmds.button('camButton', edit = True, label = 'cam')
		cmds.button('jntButton', edit = True, label = 'jnt')
		cmds.button('proxyButton', edit = True, label = 'proxy')
		cmds.button('lgtButton', edit = True, label = 'lgt')
		cmds.button('crvButton', edit = True, label = 'crv')
		cmds.button('ikButton', edit = True, label = 'ik')
		cmds.button('fkButton', edit = True, label = 'fk')
		cmds.button('setButton', edit = True, label = 'set')
		cmds.button('nrbButton', edit = True, label = 'nrb')
		cmds.button('dummyButton', edit = True, label = 'dummy')
		cmds.button('clustButton', edit = True, label = 'clust')
		cmds.button('infButton', edit = True, label = 'inf')
		cmds.button('constButton', edit = True, label = 'const')
		cmds.button('fxButton', edit = True, label = 'fx')
	elif case == 'uppercase':
		cmds.button('geoButton', edit = True, label = 'geo'.upper())
		cmds.button('grpButton', edit = True, label = 'grp'.upper())
		cmds.button('animButton', edit = True, label = 'anim'.upper())
		cmds.button('locButton', edit = True, label = 'loc'.upper())
		cmds.button('camButton', edit = True, label = 'cam'.upper())
		cmds.button('jntButton', edit = True, label = 'jnt'.upper())
		cmds.button('proxyButton', edit = True, label = 'proxy'.upper())
		cmds.button('lgtButton', edit = True, label = 'lgt'.upper())
		cmds.button('crvButton', edit = True, label = 'crv'.upper())
		cmds.button('ikButton', edit = True, label = 'ik'.upper())
		cmds.button('fkButton', edit = True, label = 'fk'.upper())
		cmds.button('setButton', edit = True, label = 'set'.upper())
		cmds.button('nrbButton', edit = True, label = 'nrb'.upper())
		cmds.button('dummyButton', edit = True, label = 'dummy'.upper())
		cmds.button('clustButton', edit = True, label = 'clust'.upper())
		cmds.button('infButton', edit = True, label = 'inf'.upper())
		cmds.button('constButton', edit = True, label = 'const'.upper())
		cmds.button('fxButton', edit = True, label = 'fx'.upper())
	else:
		sys.exit('Unexpected Error, Please contact me.')

	SaveOptionVariables()


def RemoveCharacter(sel, position, *args):
	for x in sel:
		if position == 'first':
			cmds.rename(x, x[1:])
			sys.stdout.write('Renamed "' + x + '" to "' + x[1:] + '"' + '\n')
		elif position == 'last':
			cmds.rename(x, x[0:-1])
			sys.stdout.write('Renamed "' + x + '" to "' + x[0:-1] + '"' + '.\n')
		else:
			sys.exit('Unexpected Error, Please contact me.')


def RenameShape(selS, *args):
	selL = cmds.ls(sl = True, long = True)

	for x in range(len(selL)):
		shapeL = cmds.listRelatives(selL[x], shapes = True, fullPath = True)
		shapeS = cmds.listRelatives(selL[x], shapes = True)

		if selL[x] + '|' + selS[x] + 'Shape' == shapeL[0]:
			sys.stdout.write('"' + shapeS[0] + '"' + " and it's transform have already the same name.\n")

		elif selL[x][0: len(selL[x]) - 1]+ '|' + selS[x] + 'Shape' != shapeL[0]:
			if '|' in selS[x]:
				cmds.rename(shapeL[0], selS[x].split('|')[-1] + 'Shape')
			else:
				cmds.rename(shapeL[0], selS[x] + 'Shape')
			sys.stdout.write('"' + selS[x] + '"' +  " and it's shape were synchronized.\n")
		else:
			sys.exit('Unexpected Error, Please contact me.')


def SaveOptionVariables(*args):
	cmds.optionVar(stringValue = ['batchRenamer_stringToAddTextField', cmds.textField('stringToAddTextField', query = True, text = True)])
	cmds.optionVar(intValue = ['batchRenamer_stringToAddAtPositionIntField', cmds.intField('stringToAddAtPositionIntField', query = True, value = True)])
	cmds.optionVar(stringValue = ['batchRenamer_toReplaceTextField', cmds.textField('toReplaceTextField', query = True, text = True)])
	cmds.optionVar(stringValue = ['batchRenamer_replaceWithTextField', cmds.textField('replaceWithTextField', query = True, text = True)])
	cmds.optionVar(intValue = ['batchRenamer_paddingCountIntField', cmds.intField('paddingCountIntField', query = True, value = True)])
	cmds.optionVar(intValue = ['batchRenamer_startAtIntField', cmds.intField('startAtIntField', query = True, value = True)])
	cmds.optionVar(intValue = ['batchRenamer_addAtFollowingIntField', cmds.intField('addAtFollowingIntField', query = True, value = True)])

	cmds.optionVar(intValue = ['batchRenamer_renameAndAddPaddingPaddingNumberIntField', cmds.intField('renameAndAddPaddingCountIntField', query = True, value = True)])
	cmds.optionVar(intValue = ['batchRenamer_renameAndAddPaddingStartAtIntField', cmds.intField('renameAndAddPaddingStartAtIntField', query = True, value = True)])
	cmds.optionVar(stringValue = ['batchRenamer_renameAndAddPaddingSpecialCharacterTextField', cmds.textField('renameAndAddPaddingSpecialCharacterSeparatorTextField', query = True, text = True)])
	cmds.optionVar(stringValue = ['batchRenamer_renameAndAddPaddingRenameToTextField', cmds.textField('renameAndAddPaddingRenameToTextField', query = True, text = True)])

	if cmds.radioButton('prefixRadioButton', query = True, select = True):
		prefixRadioButtonValue = True
	else:
		prefixRadioButtonValue = False

	if cmds.radioButton('suffixRadioButton', query = True, select = True):
		suffixRadioButtonValue = True
	else:
		suffixRadioButtonValue = False

	if cmds.radioButton('lowercaseRadioButton', query = True, select = True):
		lowercaseRadioButtonValue = True
	else:
		lowercaseRadioButtonValue = False

	if cmds.radioButton('uppercaseRadioButton', query = True, select = True):
		uppercaseRadioButtonValue = True
	else:
		uppercaseRadioButtonValue = False

	cmds.optionVar(intValue = ['batchRenamer_prefixRadioButton', prefixRadioButtonValue])
	cmds.optionVar(intValue = ['batchRenamer_suffixRadioButton', suffixRadioButtonValue])
	cmds.optionVar(intValue = ['batchRenamer_lowercaseRadioButton', lowercaseRadioButtonValue])
	cmds.optionVar(intValue = ['batchRenamer_uppercaseRadioButton', uppercaseRadioButtonValue])


def CheckOptionVariables(*args):
	stringToAddTextFieldValue = cmds.optionVar(query = 'batchRenamer_stringToAddTextField')
	if stringToAddTextFieldValue != 0 or stringToAddTextFieldValue != '' or stringToAddTextFieldValue != ' ' or stringToAddTextFieldValue != None:
		if stringToAddTextFieldValue == 0:
			cmds.textField('stringToAddTextField', edit = True, text = '')
		else:
			cmds.textField('stringToAddTextField', edit = True, text = stringToAddTextFieldValue)
	else:
		cmds.textField('stringToAddTextField', edit = True, text = '')

	stringToAddAtPositionIntFieldValue = cmds.optionVar(query = 'batchRenamer_stringToAddAtPositionIntField')
	if stringToAddAtPositionIntFieldValue != 0 or stringToAddAtPositionIntFieldValue != '' or stringToAddAtPositionIntFieldValue != ' ' or stringToAddAtPositionIntFieldValue != None:
		cmds.intField('stringToAddAtPositionIntField', edit = True, value = stringToAddAtPositionIntFieldValue)
	else:
		cmds.intField('stringToAddAtPositionIntField', edit = True, value = 0)

	toReplaceTextFieldValue = cmds.optionVar(query = 'batchRenamer_toReplaceTextField')
	if toReplaceTextFieldValue != 0 or toReplaceTextFieldValue != '' or toReplaceTextFieldValue != ' ' or toReplaceTextFieldValue != None:
		if toReplaceTextFieldValue == 0:
			cmds.textField('toReplaceTextField', edit = True, text = '')
		else:
			cmds.textField('toReplaceTextField', edit = True, text = toReplaceTextFieldValue)
	else:
		cmds.textField('toReplaceTextField', edit = True, text = '')

	replaceWithTextFieldValue = cmds.optionVar(query = 'batchRenamer_replaceWithTextField')
	if replaceWithTextFieldValue != 0 or replaceWithTextFieldValue != '' or replaceWithTextFieldValue != ' ' or replaceWithTextFieldValue != None:
		if replaceWithTextFieldValue == 0:
			cmds.textField('replaceWithTextField', edit = True, text = '')
		else:
			cmds.textField('replaceWithTextField', edit = True, text = replaceWithTextFieldValue)
	else:
		cmds.textField('replaceWithTextField', edit = True, text = '')

	paddingCountIntFieldValue = cmds.optionVar(query = 'batchRenamer_paddingCountIntField')
	if paddingCountIntFieldValue != 0 or paddingCountIntFieldValue != '' or paddingCountIntFieldValue != ' ' or paddingCountIntFieldValue != None:
		cmds.intField('paddingCountIntField', edit = True, value = paddingCountIntFieldValue)
	else:
		cmds.intField('paddingCountIntField', edit = True, value = 0)

	startAtIntFieldValue = cmds.optionVar(query = 'batchRenamer_startAtIntField')
	if startAtIntFieldValue != 0 or startAtIntFieldValue != '' or startAtIntFieldValue != ' ' or startAtIntFieldValue != None:
		cmds.intField('startAtIntField', edit = True, value = startAtIntFieldValue)
	else:
		cmds.intField('startAtIntField', edit = True, value = 0)

	addAtFollowingIntFieldValue = cmds.optionVar(query = 'batchRenamer_addAtFollowingIntField')
	if addAtFollowingIntFieldValue != 0 or addAtFollowingIntFieldValue != '' or addAtFollowingIntFieldValue != ' ' or addAtFollowingIntFieldValue != None:
		cmds.intField('addAtFollowingIntField', edit = True, value = addAtFollowingIntFieldValue)
	else:
		cmds.intField('addAtFollowingIntField', edit = True, value = 0)

	renameAndAddPaddingPaddingNumberIntFieldValue = cmds.optionVar(query = 'batchRenamer_renameAndAddPaddingPaddingNumberIntField')
	if renameAndAddPaddingPaddingNumberIntFieldValue != 0 or renameAndAddPaddingPaddingNumberIntFieldValue != '' or renameAndAddPaddingPaddingNumberIntFieldValue != ' ' or renameAndAddPaddingPaddingNumberIntFieldValue != None:
		cmds.intField('renameAndAddPaddingCountIntField', edit = True, value = renameAndAddPaddingPaddingNumberIntFieldValue)
	else:
		cmds.intField('renameAndAddPaddingCountIntField', edit = True, value = 0)


	renameAndAddPaddingStartAtIntFieldValue = cmds.optionVar(query = 'batchRenamer_renameAndAddPaddingStartAtIntField')
	if renameAndAddPaddingStartAtIntFieldValue != 0 or renameAndAddPaddingStartAtIntFieldValue != '' or renameAndAddPaddingStartAtIntFieldValue != ' ' or renameAndAddPaddingStartAtIntFieldValue != None:
		cmds.intField('renameAndAddPaddingStartAtIntField', edit = True, value = renameAndAddPaddingStartAtIntFieldValue)
	else:
		cmds.intField('renameAndAddPaddingStartAtIntField', edit = True, value = 0)


	renameAndAddPaddingSpecialCharacterTextFieldValue = cmds.optionVar(query = 'batchRenamer_renameAndAddPaddingSpecialCharacterTextField')
	if renameAndAddPaddingSpecialCharacterTextFieldValue:
		cmds.textField('renameAndAddPaddingSpecialCharacterSeparatorTextField', edit = True, text = renameAndAddPaddingSpecialCharacterTextFieldValue)


	renameAndAddPaddingRenameToTextFieldValue = cmds.optionVar(query = 'batchRenamer_renameAndAddPaddingRenameToTextField')
	if renameAndAddPaddingRenameToTextFieldValue:
		cmds.textField('renameAndAddPaddingRenameToTextField', edit = True, text = renameAndAddPaddingRenameToTextFieldValue)


	prefixRadioButtonValue = cmds.optionVar(query = 'batchRenamer_prefixRadioButton')
	suffixRadioButtonValue = cmds.optionVar(query = 'batchRenamer_suffixRadioButton')
	if prefixRadioButtonValue == 1 and suffixRadioButtonValue == 0:
		cmds.radioButton('prefixRadioButton', edit = True, select = True)
		cmds.radioButton('suffixRadioButton', edit = True, select = False)
	elif prefixRadioButtonValue == 0 and suffixRadioButtonValue == 1:
		cmds.radioButton('prefixRadioButton', edit = True, select = False)
		cmds.radioButton('suffixRadioButton', edit = True, select = True)
	else:
		cmds.radioButton('prefixRadioButton', edit = True, select = True)
		cmds.radioButton('suffixRadioButton', edit = True, select = False)

	lowercaseRadioButtonValue = cmds.optionVar(query = 'batchRenamer_lowercaseRadioButton')
	uppercaseRadioButtonValue = cmds.optionVar(query = 'batchRenamer_uppercaseRadioButton')
	if lowercaseRadioButtonValue == 1 and uppercaseRadioButtonValue == 0:
		cmds.radioButton('lowercaseRadioButton', edit = True, select = True)
		cmds.radioButton('uppercaseRadioButton', edit = True, select = False)
		ChangeButtonLabel('lowercase')
	elif lowercaseRadioButtonValue == 0 and uppercaseRadioButtonValue == 1:
		cmds.radioButton('lowercaseRadioButton', edit = True, select = False)
		cmds.radioButton('uppercaseRadioButton', edit = True, select = True)
		ChangeButtonLabel('uppercase')
	else:
		cmds.radioButton('lowercaseRadioButton', edit = True, select = True)
		cmds.radioButton('uppercaseRadioButton', edit = True, select = False)
		ChangeButtonLabel('lowercase')


if __name__ == '__main__':
	if not cmds.about(batch = True):
		RenameWindow()