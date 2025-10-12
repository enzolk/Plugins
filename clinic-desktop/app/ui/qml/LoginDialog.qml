import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: dialog
    modal: true
    title: qsTr("Connexion")
    standardButtons: Dialog.Ok | Dialog.Cancel

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        TextField {
            id: emailField
            placeholderText: qsTr("Email")
            focus: true
        }
        TextField {
            id: passwordField
            placeholderText: qsTr("Mot de passe")
            echoMode: TextInput.Password
        }
        CheckBox {
            text: qsTr("Rester connecté")
        }
    }
}
