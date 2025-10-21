import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Page {
    id: settingsPage
    title: qsTr("Paramètres")

    Flickable {
        anchors.fill: parent
        contentHeight: settingsLayout.implicitHeight
        clip: true

        ColumnLayout {
            id: settingsLayout
            width: parent.width
            spacing: 16
            padding: 16

            GroupBox {
                title: qsTr("Identité du cabinet")
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 8
                    TextField { Layout.fillWidth: true; placeholderText: qsTr("Nom du cabinet") }
                    TextField { Layout.fillWidth: true; placeholderText: qsTr("SIRET / SIREN") }
                    TextArea { Layout.fillWidth: true; Layout.preferredHeight: 80; placeholderText: qsTr("Adresse") }
                }
            }

            GroupBox {
                title: qsTr("Activités")
                Layout.fillWidth: true
                Repeater {
                    model: ["OST", "DRL"]
                    delegate: Frame {
                        Layout.fillWidth: true
                        ColumnLayout {
                            spacing: 8
                            padding: 12
                            Label { text: qsTr("Activité %1").arg(modelData); font.bold: true }
                            TextField { Layout.fillWidth: true; placeholderText: qsTr("Préfixe facture") }
                            TextField { Layout.fillWidth: true; placeholderText: qsTr("Compte produits") }
                            TextArea { Layout.fillWidth: true; Layout.preferredHeight: 60; placeholderText: qsTr("Mentions PDF") }
                        }
                    }
                }
            }
        }
    }
}
