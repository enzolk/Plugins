import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: dialog
    modal: true
    title: qsTr("Facture")
    standardButtons: Dialog.Save | Dialog.Cancel

    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        ComboBox {
            Layout.fillWidth: true
            model: [qsTr("Ostéopathie"), qsTr("Drainage lymphatique")]
        }
        TextField {
            Layout.fillWidth: true
            placeholderText: qsTr("Patient")
        }
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: 180
            model: 2
            delegate: Frame {
                Layout.fillWidth: true
                RowLayout {
                    anchors.fill: parent
                    spacing: 8
                    Label { text: qsTr("Acte %1").arg(index + 1) }
                    SpinBox { value: 1; from: 1; to: 10 }
                    TextField { placeholderText: qsTr("Prix HT") }
                }
            }
        }
    }
}
