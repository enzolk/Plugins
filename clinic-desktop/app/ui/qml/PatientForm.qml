import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: dialog
    modal: true
    title: qsTr("Patient")
    standardButtons: Dialog.Save | Dialog.Cancel

    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        TextField { placeholderText: qsTr("Prénom") }
        TextField { placeholderText: qsTr("Nom") }
        TextField { placeholderText: qsTr("Email") }
        TextField { placeholderText: qsTr("Téléphone") }
        TextArea {
            placeholderText: qsTr("Notes cliniques (chiffrées)")
            Layout.preferredHeight: 120
        }
    }
}
