import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    color: Qt.rgba(0.95, 0.95, 0.95, 1)
    radius: 8
    border.color: Qt.rgba(0.8, 0.8, 0.8, 1)
    border.width: 1

    Label {
        anchors.centerIn: parent
        text: qsTr("Graphique en préparation")
        color: "#555"
    }
}
