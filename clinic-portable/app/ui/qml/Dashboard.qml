import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtCharts 2.3

Page {
    id: dashboard
    title: qsTr("Tableau de bord")

    ScrollView {
        anchors.fill: parent
        ColumnLayout {
            spacing: 16
            width: parent.width

            RowLayout {
                Layout.fillWidth: true
                Repeater {
                    model: [
                        { title: qsTr("CA TTC"), value: "12 400 €" },
                        { title: qsTr("TVA collectée"), value: "1 240 €" },
                        { title: qsTr("Impayés"), value: "450 €" },
                        { title: qsTr("Consultations"), value: "42" }
                    ]
                    delegate: Frame {
                        Layout.fillWidth: true
                        Layout.preferredWidth: parent.width / 4 - 12
                        Column {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 4
                            Label {
                                text: modelData.title
                                font.bold: true
                            }
                            Label {
                                text: modelData.value
                                font.pointSize: 20
                            }
                        }
                    }
                }
            }

            Frame {
                Layout.fillWidth: true
                Layout.preferredHeight: 320
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8
                    Label {
                        text: qsTr("Évolution mensuelle du chiffre d'affaires")
                        font.bold: true
                    }
                    ChartView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        antialiasing: true
                        legend.alignment: Qt.AlignBottom
                        ValueAxis { id: axisY; min: 0; max: 1500 }
                        BarCategoryAxis { id: axisX; categories: ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin"] }
                        BarSeries {
                            axisY: axisY
                            axisX: axisX
                            BarSet { label: qsTr("OST"); values: [800, 950, 1100, 980, 1040, 1200] }
                            BarSet { label: qsTr("DRL"); values: [600, 700, 750, 820, 860, 910] }
                        }
                    }
                }
            }
        }
    }
}
