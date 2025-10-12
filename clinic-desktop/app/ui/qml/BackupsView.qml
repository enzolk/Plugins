import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Label {
            text: qsTr("Sauvegardes")
            font.pixelSize: 24
        }
        Label {
            text: qsTr("Créez des sauvegardes complètes de vos données en un clic.")
            wrapMode: Text.WordWrap
        }
        RowLayout {
            spacing: 8
            Button { text: qsTr("Créer une sauvegarde") }
            Button { text: qsTr("Restaurer") }
        }
    }
}
