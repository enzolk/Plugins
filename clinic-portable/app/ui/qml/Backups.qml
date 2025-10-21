import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Page {
    id: backupsPage
    title: qsTr("Sauvegardes")

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        RowLayout {
            spacing: 8
            Button { text: qsTr("Créer une sauvegarde") }
            Button { text: qsTr("Restaurer...") }
            Button { text: qsTr("Exporter RGPD") }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: 5
            delegate: Frame {
                width: parent.width
                padding: 12
                Column {
                    spacing: 4
                    Label { text: qsTr("Backup-%1.zip").arg(index + 1) }
                    Label { text: qsTr("Créé le 2024-01-%1").arg(index + 10) }
                }
            }
        }
    }
}
