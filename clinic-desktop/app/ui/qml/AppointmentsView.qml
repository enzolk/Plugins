import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Label {
            text: qsTr("Agenda")
            font.pixelSize: 24
        }
        Label {
            text: qsTr("Vue agenda simplifiée à implémenter.")
            wrapMode: Text.WordWrap
        }
        Calendar {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
