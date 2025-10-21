import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: patientForm
    title: qsTr("Patient")
    modal: true
    standardButtons: Dialog.Save | Dialog.Cancel
    width: 500

    contentItem: Flickable {
        contentHeight: formLayout.implicitHeight
        interactive: true
        clip: true
        ColumnLayout {
            id: formLayout
            width: parent.width
            spacing: 8
            padding: 12
            TextField { placeholderText: qsTr("Nom"); Layout.fillWidth: true }
            TextField { placeholderText: qsTr("Prénom"); Layout.fillWidth: true }
            TextField { placeholderText: qsTr("Email"); Layout.fillWidth: true }
            TextField { placeholderText: qsTr("Téléphone"); Layout.fillWidth: true }
            TextArea { placeholderText: qsTr("Adresse"); Layout.fillWidth: true; Layout.preferredHeight: 80 }
            TextField { placeholderText: qsTr("Tags (séparés par des virgules)"); Layout.fillWidth: true }
            TextArea { placeholderText: qsTr("Notes (chiffrées)"); Layout.fillWidth: true; Layout.preferredHeight: 100 }
        }
    }
}
