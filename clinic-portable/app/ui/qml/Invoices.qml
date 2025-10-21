import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Page {
    id: invoicesPage
    title: qsTr("Factures")

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            spacing: 8
            ComboBox { model: [qsTr("Toutes"), "OST", "DRL"] }
            DatePicker { }
            Button { text: qsTr("Nouvelle facture"); onClicked: invoiceForm.open() }
            Button { text: qsTr("Exporter journal") }
        }
    }

    ListView {
        anchors.fill: parent
        anchors.margins: 12
        model: 12
        delegate: Frame {
            width: parent.width
            padding: 12
            Column {
                spacing: 4
                Label { text: qsTr("Facture %1").arg(index % 2 === 0 ? "OST-2024-0001" : "DRL-2024-0002"); font.bold: true }
                Label { text: qsTr("Patient démo %1").arg(index + 1) }
                Label { text: qsTr("Total TTC : %1 €").arg(120 + index * 5) }
                RowLayout {
                    spacing: 8
                    Button { text: qsTr("PDF"); flat: true }
                    Button { text: qsTr("Paiements"); flat: true }
                    Button { text: qsTr("Avoir" ); flat: true }
                }
            }
        }
    }

    InvoiceForm { id: invoiceForm }
}
