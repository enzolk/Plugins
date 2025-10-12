import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Label {
            text: qsTr("Consultations")
            font.pixelSize: 24
        }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: 4
            delegate: ItemDelegate {
                text: qsTr("Consultation %1").arg(index + 1)
                width: ListView.view.width
            }
        }
        Button {
            text: qsTr("Nouvelle consultation")
            Layout.alignment: Qt.AlignRight
        }
    }
}
