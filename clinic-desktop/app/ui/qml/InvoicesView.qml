import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Label {
            text: qsTr("Factures")
            font.pixelSize: 24
        }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: 6
            delegate: ItemDelegate {
                width: ListView.view.width
                text: qsTr("Facture %1").arg(index + 1)
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            Button { text: qsTr("Nouvelle facture") }
            Button { text: qsTr("Exporter") }
        }
    }
}
