import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Page {
    id: consultationsPage
    title: qsTr("Consultations")

    ListView {
        anchors.fill: parent
        anchors.margins: 12
        model: 8
        delegate: Frame {
            width: parent.width
            padding: 12
            Column {
                spacing: 4
                RowLayout {
                    Label { text: qsTr("Consultation #%1").arg(index + 1); font.bold: true }
                    Label { text: qsTr("%1").arg(index % 2 === 0 ? "OST" : "DRL"); color: "#2F80ED" }
                }
                Text { text: qsTr("Patient démo %1").arg(index + 1) }
                Text { text: qsTr("Statut : %1").arg(index % 2 === 0 ? "Brouillon" : "Facturée") }
            }
        }
    }
}
