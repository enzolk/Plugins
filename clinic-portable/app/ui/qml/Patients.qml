import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Page {
    id: patientsPage
    title: qsTr("Patients")

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            spacing: 8
            TextField {
                id: searchField
                placeholderText: qsTr("Rechercher un patient...")
                Layout.fillWidth: true
            }
            ComboBox {
                id: activityFilter
                model: [qsTr("Toutes activités"), "OST", "DRL"]
            }
            Button {
                text: qsTr("Nouveau patient")
                onClicked: patientForm.open()
            }
        }
    }

    ListView {
        id: patientList
        anchors.fill: parent
        anchors.margins: 12
        model: 10
        delegate: Frame {
            width: parent.width
            padding: 12
            Column {
                spacing: 4
                Text {
                    text: qsTr("Patient démonstration %1").arg(index + 1)
                    font.bold: true
                }
                Text {
                    text: qsTr("Tags : Ostéo")
                    color: "#666"
                }
            }
        }
    }

    PatientForm {
        id: patientForm
    }
}
