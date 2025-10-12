import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        spacing: 16
        Label {
            text: qsTr("Tableau de bord")
            font.pixelSize: 24
        }
        Label {
            text: qsTr("Les statistiques apparaîtront ici.")
            wrapMode: Text.WordWrap
        }
    }
}
