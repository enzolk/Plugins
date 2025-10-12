import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Flickable {
    anchors.fill: parent
    contentWidth: parent.width
    contentHeight: column.implicitHeight

    ColumnLayout {
        id: column
        width: parent.width
        spacing: 12
        Label {
            text: qsTr("Paramètres du cabinet")
            font.pixelSize: 24
        }
        TextField { placeholderText: qsTr("Nom du cabinet") }
        TextField { placeholderText: qsTr("SIRET / SIREN") }
        TextArea {
            placeholderText: qsTr("Mentions légales")
            Layout.fillWidth: true
            Layout.preferredHeight: 120
        }
        GroupBox {
            title: qsTr("Activités")
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                spacing: 8
                Repeater {
                    model: ["Ostéopathie", "Drainage lymphatique"]
                    delegate: Frame {
                        Layout.fillWidth: true
                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 4
                            Label { text: modelData }
                            TextField { placeholderText: qsTr("Préfixe") }
                        }
                    }
                }
            }
        }
    }
}
