import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: loginDialog
    title: qsTr("Connexion")
    modal: true
    standardButtons: Dialog.Ok
    focus: true
    width: 400

    property alias email: emailField.text
    property alias password: passwordField.text
    property alias masterPassword: masterField.text

    onAccepted: {
        // TODO: call appContext.auth.authenticate via C++ bridge or Python wrapper
    }

    contentItem: ColumnLayout {
        spacing: 12
        TextField {
            id: emailField
            placeholderText: qsTr("Email")
            Layout.fillWidth: true
        }
        TextField {
            id: passwordField
            placeholderText: qsTr("Mot de passe")
            echoMode: TextInput.Password
            Layout.fillWidth: true
        }
        TextField {
            id: masterField
            placeholderText: qsTr("Mot de passe maître")
            echoMode: TextInput.Password
            Layout.fillWidth: true
        }
        Label {
            text: qsTr("Les identifiants par défaut sont admin@example.com / à définir lors du premier lancement.")
            wrapMode: Text.WordWrap
            font.pixelSize: 12
            opacity: 0.7
        }
    }
}
