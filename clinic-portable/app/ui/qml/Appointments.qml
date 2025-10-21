import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Page {
    id: appointmentsPage
    title: qsTr("Agenda")

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        ComboBox {
            model: [qsTr("Vue semaine"), qsTr("Vue mois")]
            Layout.preferredWidth: 200
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: 12
            delegate: Frame {
                width: parent.width
                padding: 12
                Column {
                    spacing: 4
                    Text { text: qsTr("%1 - Rendez-vous %2").arg("OST").arg(index + 1); font.bold: true }
                    Text { text: qsTr("Aujourd'hui 10:00 - 11:00"); color: "#666" }
                    Text { text: qsTr("Patient démo %1").arg(index + 1) }
                }
            }
        }
    }
}
