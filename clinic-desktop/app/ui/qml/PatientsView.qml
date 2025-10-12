import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        Label {
            text: qsTr("Patients")
            font.pixelSize: 24
        }
        TextField {
            placeholderText: qsTr("Rechercher un patient")
        }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: 5
            delegate: ItemDelegate {
                text: qsTr("Patient %1").arg(index + 1)
                width: ListView.view.width
            }
        }
        Button {
            text: qsTr("Nouveau patient")
            Layout.alignment: Qt.AlignRight
        }
    }
}
