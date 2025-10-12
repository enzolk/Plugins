import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "components"

Item {
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Label {
            text: qsTr("Rapports")
            font.pixelSize: 24
        }
        Label {
            text: qsTr("Visualisation des statistiques par activité.")
            wrapMode: Text.WordWrap
        }
        ProgressBar {
            value: 0.4
            Layout.fillWidth: true
        }
        ChartViewPlaceholder {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
