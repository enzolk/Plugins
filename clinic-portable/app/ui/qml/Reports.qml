import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Page {
    id: reportsPage
    title: qsTr("Rapports")

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        RowLayout {
            spacing: 8
            ComboBox { model: [qsTr("OST"), qsTr("DRL"), qsTr("Toutes")] }
            DatePicker { }
            Button { text: qsTr("Exporter CSV") }
            Button { text: qsTr("Exporter XLSX") }
        }

        TableView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: 6
            TableViewColumn { role: "month"; title: qsTr("Mois") }
            TableViewColumn { role: "ht"; title: qsTr("CA HT") }
            TableViewColumn { role: "ttc"; title: qsTr("CA TTC") }
            TableViewColumn { role: "vat"; title: qsTr("TVA") }
        }
    }
}
